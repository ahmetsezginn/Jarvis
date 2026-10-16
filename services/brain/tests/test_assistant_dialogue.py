import json

import pytest

from jarvis_brain.errors import CoreToolError, ModelOutputInvalid
from jarvis_brain.intelligence.assistant_session import AssistantSession
from jarvis_brain.intelligence.contract import IntentName
from jarvis_brain.intelligence.dialogue import FILE_FIELDS, TurnPlan, parse_turn
from jarvis_brain.intelligence.file_session import FileSession
from jarvis_brain.intelligence.legacy_runtime import LegacyBrain as JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult


def file_plan(**updates):
    args = {
        "relation": "new",
        "operation": "find",
        "kind": "file",
        "query": "",
        "location": "Masaüstü",
        "depth": "direct",
        "category": "text",
        "extension": "",
        "sort": "name",
        "name_unknown": True,
        "application": "",
    }
    args.update(updates)
    assert set(args) == set(FILE_FIELDS)
    return TurnPlan("file", 1, args)


class Core:
    def __init__(self):
        self.calls = []
        self.fail = None
        self.partial = False
        self.empty = False

    def execute_tool(self, tool, args):
        self.calls.append((tool, args.copy()))
        if self.fail:
            raise CoreToolError(self.fail, "injected")
        if tool == "search_files" and args.get("kind") == "directory":
            entries = [
                {
                    "entry_id": "root-id",
                    "name": "Masaüstü",
                    "kind": "directory",
                    "location": "private/root",
                }
            ]
        else:
            entries = (
                []
                if self.empty or "note-id" in args.get("exclude_ids", [])
                else [
                    {
                        "entry_id": "note-id",
                        "name": "random123.txt",
                        "kind": "file",
                        "location": "private/root/random123.txt",
                    }
                ]
            )
        data = (
            {"entries": entries, "total": len(entries), "partial": self.partial}
            if tool in {"search_files", "list_directory"}
            else {"opened": True}
        )
        return ToolResult("fixture", tool, "success", data, None)


class DialogueModel:
    def __init__(self, plan):
        self.plan = plan
        self.contexts = []

    def load(self):
        pass

    def plan_turn(self, text, context, state):
        self.contexts.append((context, state))
        return self.plan

    def respond(self, text, context):
        return "Bunu duyduğuma sevindim."


def test_selected_directory_listing_does_not_leak_paths_into_model_feedback():
    core = Core()
    files = FileSession(core)
    session = AssistantSession(files)
    files._observe(
        {
            "entries": [
                {
                    "entry_id": "root-id",
                    "name": "Masaüstü",
                    "kind": "directory",
                    "location": "private/root",
                }
            ],
            "total": 1,
        },
        IntentName.SEARCH_FILES,
    )
    response = session.select(
        TurnPlan("select", 1, {"number": 1, "action": "list", "application": ""}),
        "İçindekileri listele",
    )
    assert "private/root" in response.message
    assert "private/root" not in json.dumps(session.view())
    assert "root-id" not in json.dumps(session.view())


@pytest.mark.parametrize(
    "key,value",
    [
        ("query", "C:\\secrets.txt"),
        ("location", "../escape"),
        ("query", "whoami"),
        ("extension", "pdf;exe"),
        ("name_unknown", 1),
        ("depth", "shell"),
        ("category", "executable"),
        ("entry_id", "invented"),
    ],
)
def test_dialogue_fields_fail_closed(key, value):
    p = file_plan()
    p.arguments[key] = value
    with pytest.raises(ModelOutputInvalid):
        parse_turn(
            json.dumps({"move": p.move, "confidence": p.confidence, "arguments": p.arguments})
        )


@pytest.mark.parametrize("score", [True, -1, 2, float("inf"), float("nan")])
def test_dialogue_confidence_is_strict(score):
    with pytest.raises(ModelOutputInvalid):
        parse_turn(json.dumps({"move": "talk", "confidence": score, "arguments": {}}))


def test_unknown_name_uses_type_and_scope_and_never_opens():
    core = Core()
    model = DialogueModel(file_plan(operation="open"))
    brain = JarvisBrain(core, model)
    response = brain.handle_text("adı rastgele masaüstündeki notu aç")
    assert response.executed
    assert [t for t, _ in core.calls] == ["search_files", "search_files"]
    args = core.calls[-1][1]
    assert args["query"] == "*" and args["folder_id"] == "root-id"
    assert args["category"] == "text" and args["recursive"] is False
    assert "random123.txt" in response.message
    assert "root-id" not in str(model.contexts)


def test_current_message_opening_guard_overrides_stale_model_operation():
    core = Core()
    model = DialogueModel(file_plan(operation="open", query="random123", name_unknown=False))
    model.opening_requested = lambda *_: False
    brain = JarvisBrain(core, model)
    brain.handle_text("random123 dosyasından bahsediyorum")
    assert [tool for tool, _ in core.calls] == ["search_files", "search_files"]
    assert not any(tool.startswith("open_") for tool, _ in core.calls)


@pytest.mark.parametrize(
    "plan", [TurnPlan("unsupported", 1, {}), file_plan(operation="unsupported")]
)
def test_unavailable_operations_never_search_or_open_as_a_substitute(plan):
    core = Core()
    response = JarvisBrain(core, DialogueModel(plan)).handle_text("dosyamı internete yükle")
    assert not response.executed and not core.calls


def test_invalid_new_plan_discards_old_page_before_a_later_numeric_choice():
    core = Core()
    model = DialogueModel(file_plan())
    brain = JarvisBrain(core, model)
    brain.handle_text("notumu bul")
    model.plan = TurnPlan("file", 1, {"query": "unvalidated"})
    with pytest.raises(ModelOutputInvalid):
        brain.handle_text("başka bir dosyamı arıyorum")
    core.calls.clear()
    response = brain.handle_text("1")
    assert not response.executed and not core.calls
    assert brain._assistant.goal is None


@pytest.mark.parametrize("text", ["Steam'i açma", "bunu açmayın", "Don't open that app"])
def test_explicit_opening_prohibitions_precede_model_and_core(text):
    core = Core()
    model = DialogueModel(TurnPlan("app", 1, {"query": "invented"}))
    response = JarvisBrain(core, model).handle_text(text)
    assert not response.executed and not core.calls and not model.contexts


def test_reject_clears_name_hypothesis_and_excludes_exact_previous_ids():
    core = Core()
    model = DialogueModel(file_plan(query="note", name_unknown=False))
    brain = JarvisBrain(core, model)
    brain.handle_text("notu bul")
    core.calls.clear()
    model.plan = file_plan(relation="reject", location="", depth="keep")
    response = brain.handle_text("bunlar değil, adı rastgeleydi")
    assert core.calls[-1][1]["exclude_ids"] == ["note-id"]
    assert core.calls[-1][1]["query"] == "*"
    assert not any(t.startswith("open_") for t, _ in core.calls)
    assert "hatırlıyor musun" in response.message


def test_explanation_and_chat_after_results_never_replay_tools():
    core = Core()
    model = DialogueModel(file_plan())
    brain = JarvisBrain(core, model)
    brain.handle_text("masaüstündeki notu bul")
    for move, text in [("explain", "neden"), ("talk", "bugün mutluyum")]:
        core.calls.clear()
        model.plan = TurnPlan(move, 1, {})
        response = brain.handle_text(text)
        assert not core.calls and not response.executed
    assert response.intent is IntentName.RESPOND
    assert brain._files.model_candidates()[0].name == "random123.txt"


def test_direct_listing_cannot_degenerate_to_recursive_search():
    core = Core()
    brain = JarvisBrain(core, DialogueModel(file_plan(operation="list", category="any")))
    brain.handle_text("masaüstünde doğrudan neler var")
    assert [t for t, _ in core.calls] == ["search_files", "list_directory"]
    assert core.calls[-1][1]["entry_id"] == "root-id"


def test_scope_only_update_retains_listing_operation_and_trusted_folder():
    core = Core()
    model = DialogueModel(file_plan(operation="list", query="Masaüstü", category="any"))
    brain = JarvisBrain(core, model)
    brain.handle_text("masaüstünde ne var")
    core.calls.clear()
    model.plan = file_plan(
        relation="refine",
        operation="keep",
        query="",
        kind="any",
        location="",
        category="any",
        name_unknown=False,
    )
    brain.handle_text("alt klasörlere girme")
    assert [t for t, _ in core.calls] == ["list_directory"]


def test_new_search_scope_replaces_old_folder_for_relative_followups():
    core = Core()
    model = DialogueModel(file_plan())
    brain = JarvisBrain(core, model)
    brain._files._set_scope({"entry_id": "old-root", "name": "İndirilenler", "kind": "directory"})
    brain.handle_text("masaüstündeki notumu bul")
    assert brain._files._scope["entry_id"] == "root-id"
    core.calls.clear()
    model.plan = file_plan(
        relation="refine", query="random123", location="relative", name_unknown=False
    )
    brain.handle_text("orada random123 dosyasını bul")
    assert core.calls[-1][1]["folder_id"] == "root-id"


def test_refresh_discards_goal_scope_and_rejections_when_catalog_ids_change():
    class RefreshCore(Core):
        def execute_tool(self, tool, arguments):
            if tool in {"file_catalog_status", "refresh_file_catalog"}:
                self.calls.append((tool, arguments))
                return ToolResult(
                    "refresh",
                    tool,
                    "success",
                    {
                        "indexed": True,
                        "roots": [],
                        "files": 1,
                        "directories": 1,
                        "partial": False,
                    },
                    None,
                )
            return super().execute_tool(tool, arguments)

    core = RefreshCore()
    model = DialogueModel(file_plan())
    brain = JarvisBrain(core, model)
    brain.handle_text("notumu bul")
    model.plan = TurnPlan("refresh", 1, {})
    brain.handle_text("dosya kataloğunu yenile")
    assert brain._assistant.goal is None and brain._assistant.scope is None
    assert brain._files._scope is None and brain._files._entries == ()


def test_unknown_location_needs_a_focused_question_and_zero_tools():
    core = Core()
    brain = JarvisBrain(core, DialogueModel(file_plan(location="")))
    response = brain.handle_text("adını da yerini de hatırlamıyorum")
    assert "klasör" in response.message and not core.calls


def test_chat_preserves_pending_goal_without_execution_or_renewing_lifetime():
    core = Core()
    model = DialogueModel(file_plan(location=""))
    brain = JarvisBrain(core, model)
    brain.handle_text("adını hatırlamıyorum")
    assert brain._assistant.view()["pending_slot"] == "location"
    expires = brain._assistant.expires
    model.plan = TurnPlan("talk", 1, {})
    brain.handle_text("bugün çok mutluyum")
    assert brain._assistant.view()["pending_slot"] == "location"
    assert brain._assistant.expires == expires
    assert brain._assistant.scope is None
    assert not core.calls


def test_result_discussion_receives_metadata_and_can_resume_selection():
    core = Core()
    model = DialogueModel(file_plan())
    brain = JarvisBrain(core, model)
    brain.handle_text("masaüstündeki notu bul")
    page_deadline = brain._files._expires
    core.calls.clear()
    captured = []

    def respond(text, context):
        captured.append(context)
        return "Listedeki metin belgesi olabilir; içeriğini bilmiyorum."

    model.respond = respond
    model.plan = TurnPlan("talk", 1, {})
    brain.handle_text("bir öneride bulunur musun")
    assert not core.calls
    assert captured[0].file_candidates[0].name == "random123.txt"
    assert "private/root" not in repr(captured[0])
    assert "note-id" not in repr(captured[0])
    assert brain._files._expires == page_deadline

    brain.handle_text("1")
    assert core.calls == [("open_file", {"entry_id": "note-id"})]


@pytest.mark.parametrize("sort,extension", [("largest", ""), ("newest", ""), ("name", "pdf")])
def test_global_metadata_browsing_has_meaningful_constraints(sort, extension):
    core = Core()
    brain = JarvisBrain(
        core,
        DialogueModel(
            file_plan(
                location="",
                depth="keep",
                category="any",
                name_unknown=False,
                sort=sort,
                extension=extension,
            )
        ),
    )
    response = brain.handle_text("dosyaları bu ölçüte göre göster")
    assert response.executed
    assert [tool for tool, _ in core.calls] == ["search_files"]
    assert not any(tool.startswith("open_") for tool, _ in core.calls)


def test_unscoped_new_goal_drops_prior_directory_binding():
    core = Core()
    files = FileSession(core)
    session = AssistantSession(files)
    session.file_turn(file_plan(), "Masaüstündeki notları bul")
    assert files._scope is not None
    response = session.file_turn(
        file_plan(query="budget", location="", depth="keep", name_unknown=False),
        "Bütçeyi bul",
    )
    assert "folder_id" not in core.calls[-1][1]
    assert files._scope is None
    assert "Aktif arama klasörü" not in response.message


@pytest.mark.parametrize("sort", ["newest", "largest"])
def test_scope_refinement_preserves_order_and_explicit_name_order_can_replace_it(sort):
    core = Core()
    session = AssistantSession(FileSession(core))
    session.file_turn(file_plan(sort=sort), "Dosyaları bu sırada bul")
    session.file_turn(
        file_plan(relation="refine", operation="keep", sort="keep", depth="recursive"),
        "Alt klasörlere de bak",
    )
    assert core.calls[-1][1]["sort"] == sort
    session.file_turn(
        file_plan(relation="refine", operation="keep", sort="name"), "Ada göre sırala"
    )
    assert core.calls[-1][1]["sort"] == "name"


@pytest.mark.parametrize(
    "failure",
    ["policy_denied", "invalid_arguments", "unknown_tool", "ipc_unavailable", "permission_denied"],
)
def test_failed_discovery_has_no_open_retry_or_stale_selection(failure):
    core = Core()
    core.fail = failure
    brain = JarvisBrain(core, DialogueModel(file_plan()))
    response = brain.handle_text("notumu bul")
    assert not response.executed and len(core.calls) == 1
    assert brain._files.model_candidates() == ()
    assert "açıldı" not in response.message


@pytest.mark.parametrize("reset", ["/reset", "iptal"])
def test_reset_cancel_and_expiry_drop_private_task_state(reset):
    core = Core()
    model = DialogueModel(file_plan())
    brain = JarvisBrain(core, model)
    brain.handle_text("notu bul")
    model.plan = TurnPlan("cancel", 1, {})
    brain.handle_text(reset)
    assert brain._assistant.goal is None
    assert brain._files.model_candidates() == ()
    now = [0]
    session = AssistantSession(FileSession(core), clock=lambda: now[0])
    session.file_turn(file_plan(), "notu bul")
    now[0] = 121
    assert session.view()["goal"] is None


def test_empty_partial_search_preserves_limits_and_asks_next_clue():
    core = Core()
    core.empty = core.partial = True
    brain = JarvisBrain(core, DialogueModel(file_plan(query="receipt", name_unknown=False)))
    response = brain.handle_text("masaüstündeki makbuzumu bul")
    assert len(core.calls) == 3  # resolve folder, name, bounded same-scope type recovery
    assert "Tarama kısmi" in response.message
    assert "Başka bir klasör" in response.message
    assert brain._assistant.view()["pending_slot"] == "clue"


@pytest.mark.parametrize("number", [0, 1, 20])
def test_selection_without_current_page_never_falls_back_to_search(number):
    core = Core()
    p = TurnPlan("select", 1, {"number": number, "action": "open", "application": ""})
    brain = JarvisBrain(core, DialogueModel(p))
    response = brain.handle_text("onu aç")
    assert not response.executed and not core.calls


@pytest.mark.parametrize("code", ["permission_denied", "execution_failed"])
def test_os_errors_do_not_claim_a_changed_catalog_or_leak_native_paths(code):
    response = FileSession._failure(CoreToolError(code, "private/native/path"))
    assert not response.executed
    assert "Katalog değişmiş" not in response.message
    assert "private/native/path" not in response.message


@pytest.mark.parametrize("text", ["21. olanı aç", "0. dosyayı aç", "-2. olanı aç"])
def test_invalid_numbered_address_is_rejected_before_model_planning(text):
    model = DialogueModel(TurnPlan("status", 1, {}))
    core = Core()
    response = JarvisBrain(core, model).handle_text(text)
    assert not response.executed and not core.calls and model.contexts == []
