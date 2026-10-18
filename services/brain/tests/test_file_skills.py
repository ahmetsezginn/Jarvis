import pytest

from jarvis_brain.errors import CoreToolError, ModelOutputInvalid
from jarvis_brain.intelligence.contract import (
    FileCandidate,
    IntentContext,
    IntentName,
    IntentResult,
)
from jarvis_brain.intelligence.file_session import FileSession
from jarvis_brain.intelligence.legacy_runtime import LegacyBrain as JarvisBrain
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.parser import parse_model_output
from jarvis_brain.intelligence.request_routing import RequestKind, RequestRoute
from jarvis_brain.ipc.protocol import ToolResult


class Core:
    def __init__(self):
        self.calls = []
        self.entries = [
            {
                "entry_id": "rust-file-1",
                "name": "Bütçe.xlsx",
                "kind": "file",
                "location": "Documents/Bütçe.xlsx",
            },
            {
                "entry_id": "rust-file-2",
                "name": "Bütçe.xlsx",
                "kind": "file",
                "location": "Documents/Alt/Bütçe.xlsx",
            },
        ]
        self.stale = False

    def execute_tool(self, tool, args):
        self.calls.append((tool, args))
        if tool in {"search_files", "list_directory"}:
            data = {"entries": self.entries, "total": len(self.entries), "partial": False}
        elif tool == "resolve_app":
            data = {"resolved": True, "app": {"app_id": "rust-chrome", "name": "Google Chrome"}}
        elif tool in {
            "open_file",
            "open_directory",
            "open_containing_folder",
            "open_file_with_app",
        }:
            if self.stale:
                raise CoreToolError("invalid_arguments", "stale")
            data = {"opened": True, "entry": {"name": "Belgeler"}}
        else:
            data = {
                "indexed": tool == "refresh_file_catalog",
                "roots": [{"name": "Belgeler"}],
                "files": 2,
                "directories": 1,
                "partial": True,
            }
        return ToolResult("id", tool, "success", data, None)


def brain(core, intent=IntentName.SEARCH_FILES, confidence=1):
    return JarvisBrain(core, FakeIntentModel(IntentResult(intent, confidence, {"query": "bütçe"})))


def test_search_and_explicit_selection_use_only_core_ids():
    core = Core()
    runtime = brain(core)
    response = runtime.handle_text("bütçe dosyasını bul")
    assert "2 sonuç" in response.message
    assert all("rust-file" not in t.assistant for t in runtime._conversation.snapshot())
    assert runtime.handle_text("ikincisini aç").executed
    assert core.calls[-1] == ("open_file", {"entry_id": "rust-file-2"})


def test_duplicate_open_requires_choice_and_containing_folder_selection():
    core = Core()
    runtime = brain(core, IntentName.OPEN_FILE)
    response = runtime.handle_text("bütçe dosyasını aç")
    assert response.intent is IntentName.CLARIFY
    assert [c[0] for c in core.calls] == ["search_files"]
    assert runtime.handle_text("ikincisinin bulunduğu klasörü aç").executed
    assert core.calls[-1] == ("open_containing_folder", {"entry_id": "rust-file-2"})


@pytest.mark.parametrize("text", ["bütçe dosyasını açma", "do not open budget", "iptal"])
def test_negation_cannot_launch_even_if_model_requests_open(text):
    core = Core()
    core.entries = core.entries[:1]
    response = brain(core, IntentName.OPEN_FILE).handle_text(text)
    assert not response.executed
    assert core.calls == []


def test_low_confidence_and_conversation_never_dispatch_file_tools():
    core = Core()
    assert not brain(core, confidence=0.1).handle_text("bul").executed
    model = FakeIntentModel(
        IntentResult(IntentName.OPEN_FILE, 1, {"query": "bütçe"}),
        request_route=RequestRoute(RequestKind.CONVERSATION, 1),
    )
    assert not JarvisBrain(core, model).handle_text("dosya nedir").executed
    assert core.calls == []


def test_stale_selection_consumed_reset_and_expiry():
    core = Core()
    runtime = brain(core)
    runtime.handle_text("bütçe dosyasını bul")
    core.stale = True
    assert not runtime.handle_text("1 aç").executed
    assert runtime._files._entries == ()
    core.stale = False
    runtime.handle_text("bütçe dosyasını bul")
    runtime.reset_context()
    assert runtime._files._entries == ()
    now = [0.0]
    session = FileSession(core, lambda: now[0])
    session.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "bütçe"}), "bul")
    now[0] = 121
    assert session.handle("2 aç") is None


def test_unrelated_turn_clears_selection_and_does_not_leak_locations_into_history():
    core = Core()
    runtime = brain(core)
    runtime.handle_text("bütçe dosyasını bul")
    assert "Documents/" not in runtime._conversation.snapshot()[0].assistant
    assert runtime._files.handle("nasılsın") is None
    assert runtime._files._entries == ()


def test_inventory_refresh_and_folder_listing_are_core_backed():
    core = Core()
    runtime = JarvisBrain(
        core, FakeIntentModel(IntentResult(IntentName.FILE_CATALOG_STATUS, 1, {}))
    )
    response = runtime.handle_text("bilgisayarımda ne var")
    assert "2 dosya" in response.message and "kısmi" in response.message
    assert [c[0] for c in core.calls] == ["file_catalog_status", "refresh_file_catalog"]
    core.entries = [
        {
            "entry_id": "rust-folder",
            "name": "Belgeler",
            "kind": "directory",
            "location": "Documents",
        }
    ]
    brain(core, IntentName.LIST_FOLDER).handle_text("Belgeler içinde ne var")
    assert core.calls[-1] == ("list_directory", {"entry_id": "rust-folder", "limit": 20})


def test_search_filters_forwarded_without_model_ids_and_page_selection():
    core = Core()
    session = FileSession(core)
    session.execute(
        IntentResult(
            IntentName.SEARCH_FILES,
            1,
            {"query": "*", "sort": "largest", "extension": "xlsx", "kind": "file"},
        ),
        "bul",
    )
    assert core.calls[0][1]["sort"] == "largest"
    assert core.calls[0][1]["extension"] == "xlsx"
    data = {"entries": core.entries, "total": 30, "offset": 0, "partial": False}
    session._observe(data, IntentName.SEARCH_FILES, ("search_files", {"query": "*", "limit": 20}))
    assert session.handle("sonraki sayfa") is not None
    assert core.calls[-1][1]["offset"] == 20


def test_file_negation_blocks_wrong_application_prediction():
    core = Core()
    runtime = brain(core, IntentName.OPEN_APPLICATION)
    assert not runtime.handle_text("rapor dosyasını açma").executed
    assert not core.calls


@pytest.mark.parametrize(
    "output",
    [
        '{"intent":"open_file","confidence":1,"arguments":{"entry_id":"made-up"}}',
        '{"intent":"open_directory","confidence":1,"arguments":{"query":"C:\\\\Windows"}}',
        '{"intent":"open_file","confidence":1,"arguments":{"query":"launch.ps1"}}',
        '{"intent":"search_files","confidence":1,"arguments":{"query":"report","path":"elsewhere"}}',
    ],
)
def test_model_cannot_supply_ids_paths_or_execution_targets(output):
    with pytest.raises(ModelOutputInvalid):
        parse_model_output(output)


def cv_entries():
    return [
        {
            "entry_id": "en",
            "name": "Ahmet-Sezgin-CV-EN.pdf",
            "kind": "file",
            "location": "fixture/en",
        },
        {
            "entry_id": "tr",
            "name": "Ahmet-Sezgin-CV-TR.pdf",
            "kind": "file",
            "location": "fixture/tr",
        },
        {"entry_id": "other-tr", "name": "CV-tr.pdf", "kind": "file", "location": "fixture/other"},
    ]


def test_relative_search_retains_opened_folder_then_unique_found_folder():
    core = Core()
    session = FileSession(core)
    core.entries = [
        {
            "entry_id": "downloads",
            "name": "İndirilenler",
            "kind": "directory",
            "location": "fixture/downloads",
        }
    ]
    session.execute(
        IntentResult(IntentName.OPEN_DIRECTORY, 1, {"query": "indirilenler"}),
        "indirilenler klasörünü aç",
    )
    core.entries = [
        {
            "entry_id": "cvfolder",
            "name": "cvfolder",
            "kind": "directory",
            "location": "fixture/cvfolder",
        }
    ]
    assert session.handle("orada cv min olduğu bir klasör var onu bulur musun") is None
    session.execute(
        IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv", "kind": "directory"}),
        "orada cv min olduğu bir klasör var onu bulur musun",
    )
    assert core.calls[-1][1]["folder_id"] == "downloads"
    core.entries = cv_entries()[:2]
    assert session.handle("aynen orada benim cvim var onu bana bulur musun") is None
    session.execute(
        IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv", "kind": "file"}),
        "aynen orada benim cvim var onu bana bulur musun",
    )
    assert core.calls[-1][1]["folder_id"] == "cvfolder"


def test_partial_name_punctuation_and_extension_select_existing_core_id():
    core = Core()
    core.entries = cv_entries()
    runtime = brain(core)
    runtime.handle_text("cv dosyalarını bul")
    assert runtime.handle_text("ahmet sezgin cv tr yi açar mısın").executed
    assert core.calls[-1] == ("open_file", {"entry_id": "tr"})


def test_google_clarification_yes_preserves_target_and_application():
    core = Core()
    core.entries = cv_entries()[:2]
    runtime = brain(core)
    runtime.handle_text("cv dosyalarını bul")
    before = len(core.calls)
    response = runtime.handle_text("tr olanı google ile aç")
    assert "Google Chrome" in response.message and not response.executed
    assert len(core.calls) == before
    assert runtime.handle_text("evet").executed
    assert core.calls[-2:] == [
        ("resolve_app", {"query": "Google Chrome"}),
        ("open_file_with_app", {"entry_id": "tr", "app_id": "rust-chrome"}),
    ]
    assert runtime._files._entries == ()
    assert runtime._files._confirmation is None


def test_ambiguous_tr_never_opens_until_unique_choice():
    core = Core()
    core.entries = cv_entries()
    runtime = brain(core)
    runtime.handle_text("cv dosyalarını bul")
    response = runtime.handle_text("tr olanı google ile aç")
    assert "2 sonuç" in response.message
    assert not runtime.handle_text("evet").executed
    assert [call[0] for call in core.calls] == ["search_files"]
    assert runtime.handle_text("ahmet sezgin cv tr yi açar mısın").executed
    assert core.calls[-1][1]["entry_id"] == "tr"


@pytest.mark.parametrize("interruption", ["iptal", "/reset", "nasılsın"])
def test_pending_application_confirmation_cleared_by_other_turns(interruption):
    core = Core()
    core.entries = cv_entries()[:2]
    runtime = brain(core)
    runtime.handle_text("cv bul")
    runtime.handle_text("tr olanı google ile aç")
    runtime.handle_text(interruption)
    runtime.handle_text("evet")
    assert all(call[0] != "open_file_with_app" for call in core.calls)


def test_google_docs_unsupported_keeps_list_for_next_local_open():
    core = Core()
    core.entries = cv_entries()
    runtime = brain(core)
    runtime.handle_text("cv bul")
    assert "yükleme" in runtime.handle_text("tr olanı google docs ile aç").message
    assert runtime.handle_text("ahmet sezgin cv tr yi açar mısın").executed
    assert core.calls[-1] == ("open_file", {"entry_id": "tr"})


@pytest.mark.parametrize("application", ["WriterPro", "Google Docs"])
def test_numbered_unsupported_app_keeps_binding_for_default_open(application):
    core = Core()
    session = FileSession(core)
    session.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "budget"}), "find budget")
    core.calls.clear()
    rejected = session.select_displayed(
        IntentResult(
            IntentName.SELECT_FILE,
            1,
            {"number": 2, "action": "open", "application": application},
        )
    )
    assert not rejected.executed and not core.calls
    assert session.accepts_number(2)
    opened = session.select_displayed(
        IntentResult(IntentName.SELECT_FILE, 1, {"number": 2, "action": "open", "application": ""})
    )
    assert opened.executed
    assert core.calls == [("open_file", {"entry_id": "rust-file-2"})]
    assert not session.accepts_number(2)


def test_rejected_numbered_request_never_extends_binding_expiry():
    now = [0.0]
    core = Core()
    session = FileSession(core, lambda: now[0])
    session.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "budget"}), "find budget")
    core.calls.clear()
    now[0] = 110
    session.select_displayed(
        IntentResult(
            IntentName.SELECT_FILE, 1, {"number": 1, "action": "open", "application": "WriterPro"}
        )
    )
    assert session.accepts_number(1)
    now[0] = 121
    response = session.select_displayed(
        IntentResult(IntentName.SELECT_FILE, 1, {"number": 1, "action": "open", "application": ""})
    )
    assert not response.executed and not core.calls


def test_scope_and_confirmation_expiry_do_not_dispatch():
    core = Core()
    core.entries = cv_entries()[:2]
    now = [0.0]
    session = FileSession(core, lambda: now[0])
    session.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "bul")
    session.handle("tr olanı google ile aç")
    now[0] = 121
    assert session.handle("evet") is None
    assert [call[0] for call in core.calls] == ["search_files"]


def test_relative_reference_without_known_folder_never_searches_globally():
    core = Core()
    response = brain(core).handle_text("orada cv dosyamı bul")
    assert "Hangi klasör" in response.message
    assert not response.executed and not core.calls


def test_multiple_folders_cannot_be_implicitly_selected_by_relative_search():
    core = Core()
    core.entries = [
        {
            "entry_id": f"folder-{i}",
            "name": f"CV folder {i}",
            "kind": "directory",
            "location": f"fixture/{i}",
        }
        for i in range(2)
    ]
    runtime = brain(core)
    runtime.handle_text("cv klasörlerini bul")
    response = runtime.handle_text("orada cv dosyamı bul")
    assert "Hangi klasör" in response.message
    assert len(core.calls) == 1


def test_single_displayed_file_pronoun_and_explicit_chrome_open():
    core = Core()
    core.entries = cv_entries()[1:2]
    runtime = brain(core)
    runtime.handle_text("cv tr bul")
    assert runtime.handle_text("onu chrome ile aç").executed
    assert core.calls[-1] == ("open_file_with_app", {"entry_id": "tr", "app_id": "rust-chrome"})


def test_changed_google_target_invalidates_earlier_confirmation():
    core = Core()
    core.entries = cv_entries()
    runtime = brain(core)
    runtime.handle_text("cv bul")
    runtime.handle_text("ahmet sezgin cv tr google ile aç")
    assert runtime._files._confirmation is not None
    runtime.handle_text("tr olanı google ile aç")
    assert runtime._files._confirmation is None
    assert not runtime.handle_text("evet").executed
    assert [tool for tool, _ in core.calls] == ["search_files"]


@pytest.mark.parametrize("extension", ["pdf", "txt", "docx", "jpg"])
def test_model_semantic_selection_opens_default_association(extension):
    core = Core()
    core.entries = [
        {
            "entry_id": "trusted-tr",
            "name": f"CV-TR.{extension}",
            "kind": "file",
            "location": "private/location",
        }
    ]

    class SeeingModel(FakeIntentModel):
        def predict(self, text, context):
            self.context = context
            return super().predict(text, context)

    model = SeeingModel(
        IntentResult(IntentName.OPEN_FILE, 1, {"query": f"CV-TR.{extension}", "application": ""})
    )
    runtime = JarvisBrain(core, model)
    runtime._files.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "cv bul")
    core.calls.clear()
    response = runtime.handle_text("tr olan benimkisi onu açar mısın")
    assert response.executed
    assert core.calls == [("open_file", {"entry_id": "trusted-tr"})]
    assert model.context.file_candidates == (FileCandidate(f"CV-TR.{extension}", "file", 1),)
    from jarvis_brain.intelligence.prompts import build_user_payload

    payload = build_user_payload("aç", model.context)
    assert "trusted-tr" not in payload and "private/location" not in payload


def test_model_can_choose_explicit_browser_but_ambiguity_never_selects_first():
    core = Core()
    core.entries = cv_entries()
    runtime = brain(core)
    runtime._files.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "cv bul")
    core.calls.clear()
    response = runtime._files.execute(
        IntentResult(IntentName.OPEN_FILE, 1, {"query": "tr", "application": "Google Chrome"}),
        "Türkçe olanı tarayıcıyla aç",
    )
    assert not response.executed
    assert len(runtime._files._entries) == 2 and core.calls == []
    response = runtime._files.execute(
        IntentResult(
            IntentName.OPEN_FILE,
            1,
            {"query": "Ahmet-Sezgin-CV-TR.pdf", "application": "Microsoft Edge"},
        ),
        "Ahmet Sezgin Türkçe CVyi Edge üzerinden göster",
    )
    assert response.executed
    assert core.calls == [
        ("resolve_app", {"query": "Microsoft Edge"}),
        ("open_file_with_app", {"entry_id": "tr", "app_id": "rust-chrome"}),
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "CV", "application": "cmd.exe"},
        {"query": "CV", "application": "C:\\Chrome"},
        {"query": "CV", "application": "Chrome; evil"},
        {"query": "CV", "app_id": "invented"},
    ],
)
def test_open_file_application_is_semantic_data_never_machine_authority(arguments):
    from jarvis_brain.intelligence.contract import validate_intent_object

    with pytest.raises(ModelOutputInvalid):
        validate_intent_object(
            {"intent": "open_file", "confidence": 1, "arguments": arguments}, model_output=True
        )


def test_conversation_after_unmatched_file_reference_never_executes_tools():
    core = Core()
    runtime = JarvisBrain(
        core,
        FakeIntentModel(
            IntentResult(IntentName.OPEN_FILE, 1, {"query": "CV"}),
            request_route=RequestRoute(RequestKind.CONVERSATION, 1),
        ),
    )
    runtime._files.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "cv bul")
    core.calls.clear()
    response = runtime.handle_text("CV nedir, bana anlat")
    assert response.intent is IntentName.RESPOND and core.calls == []
    assert not runtime._files.model_candidates()


def test_candidate_context_is_bounded_and_expires():
    core = Core()
    core.entries = [
        {
            "entry_id": str(i),
            "name": "a" * 200 + str(i) + ".pdf",
            "kind": "file",
            "location": "private/location",
        }
        for i in range(20)
    ]
    now = [0.0]
    session = FileSession(core, lambda: now[0])
    session.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "*"}), "bul")
    candidates = session.model_candidates()
    assert 0 < sum(len(c.name) for c in candidates) <= 1200
    IntentContext(file_candidates=candidates)
    now[0] = 121
    assert session.model_candidates() == ()


@pytest.mark.parametrize(
    "candidates",
    [
        (FileCandidate("CV.pdf", "program"),),
        (FileCandidate("a" * 257, "file"),),
        tuple(FileCandidate("CV.pdf", "file") for _ in range(21)),
    ],
)
def test_invalid_file_candidate_context_is_rejected(candidates):
    with pytest.raises(ValueError):
        IntentContext(file_candidates=candidates)


def test_file_planning_ignores_assistant_capability_claims_but_keeps_chat_history():
    from jarvis_brain.intelligence.contract import BrainResponse

    core = Core()
    runtime = brain(core)
    runtime._files.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "cv bul")
    runtime._conversation.observe(
        "TR dosyası",
        BrainResponse(IntentName.RESPOND, 1, "conversation", False, "Only Chrome can open files"),
    )
    context = runtime._model_context("Türkçe dosyayı aç")
    assert context.file_candidates
    assert all(t.assistant == "" for t in context.history)
    assert runtime._conversation.snapshot()[-1].assistant == "Only Chrome can open files"
    assert runtime._model_context("orada dosyayı bul").file_candidates == ()
