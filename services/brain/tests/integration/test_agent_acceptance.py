"""Real-model, cross-domain behavioral acceptance. Invented metadata; no OS launches.

Expected identities and forbidden effects are fixed independently of model/tool sequence.
"""

import os

import pytest
from scripts.evaluation.agent_test_model import test_model
from scripts.evaluation.analyze_file_assistance import SyntheticCore

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult

pytestmark = pytest.mark.integration

DOCUMENTS = (
    ("lease", "kira-sozlesmesi.docx"),
    ("statistics", "istatistik-ders-notlari.txt"),
    ("garden", "bahce-plani.png"),
    ("budget", "aile-butcesi.xlsx"),
    ("recipe", "mercimek-corbasi-tarifi.txt"),
    ("recording", "piyano-kaydi.wav"),
    ("photo", "mezuniyet-fotografi.jpg"),
    ("presentation", "pazarlama-sunumu.txt"),
)


class Core(SyntheticCore):
    def __init__(self):
        super().__init__()
        self.entries.extend(
            {"entry_id": id_, "name": name, "kind": "file", "location": f"Downloads/{name}"}
            for id_, name in DOCUMENTS
        )
        self.entries.extend(
            {
                "entry_id": f"noise-{i}",
                "name": f"baska-belge-{i}.pdf",
                "kind": "file",
                "location": f"Documents/baska-belge-{i}.pdf",
            }
            for i in range(25)
        )

    def execute_tool(self, tool, args):
        if tool in {"resolve_app", "open_app", "open_file_with_app", "refresh_app_catalog"}:
            self.calls.append({"tool": tool, "arguments": dict(args)})
            data = {"resolved": True, "app": {"app_id": "fixture-browser"}}
            if tool == "refresh_app_catalog":
                data = {"count": 2}
            elif tool != "resolve_app":
                data = {"opened": True}
            return ToolResult("fixture", tool, "success", data, None)
        return super().execute_tool(tool, args)


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_ASSISTANT_TESTS") != "1":
        pytest.skip("opt-in real model agent acceptance")
    value = test_model(os.environ.get("JARVIS_AGENT_TEST_PROFILE", "qwen3-4b"))
    yield value
    value.unload()


def runtime(model):
    core = Core()
    return JarvisBrain(core, model), core


def turn(brain, core, text):
    core.calls.clear()
    brain._model.events.clear()
    response = brain.handle_text(text)
    print(text, "=>", response.message, core.calls)
    print("model trace", brain._model.events)
    return response


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ev sahibimle yaptığımız kira sözleşmesini bir yere kaydettim ama bulamıyorum", "lease"),
        ("İstatistik dersinde tuttuğum notlar nereye gitti acaba, bulmama yardım et", "statistics"),
        ("Bahçe planımı kaybetmişim bilgisayarda bir bakabilir misin", "garden"),
        ("Aile bütçesi için hazırladığım tabloyu arıyorum", "budget"),
        ("Mercimek çorbası tarifini yazmıştım hangi dosyadaydı bulur musun", "recipe"),
        ("Piyano kaydımı bilgisayarda bulamıyorum yardım eder misin", "recording"),
        ("Mezuniyet fotoğrafımı bulsana", "photo"),
        ("Pazarlama sunumunu arıyorum, uzantısını hatırlamıyorum", "presentation"),
    ],
)
def test_discovery_precision_across_topics_and_formats(model, text, expected):
    brain, core = runtime(model)
    turn(brain, core, text)
    assert {e["entry_id"] for e in brain._files._entries} == {expected}
    assert core.calls and all(
        c["tool"] in {"search_files", "file_catalog_status"} for c in core.calls
    )
    assert all(
        c["arguments"]["query"] not in {"*", ""} for c in core.calls if c["tool"] == "search_files"
    )


@pytest.mark.parametrize("id_,name", DOCUMENTS)
def test_default_open_is_independent_of_file_format(model, id_, name):
    brain, core = runtime(model)
    brain._agent.builtins.find_files({"query": name})  # Identity setup, not an NL inference.
    response = turn(brain, core, "Evet bu benim aradığım, onu açar mısın")
    assert response.executed
    assert core.calls == [{"tool": "open_file", "arguments": {"entry_id": id_}}]


@pytest.mark.parametrize(
    "text",
    [
        "Steam'i açma",
        "Dosyayı nasıl açabilirim, adımlarını anlat",
        "Dosyalarımı bulabiliyor musun, neler yapabiliyorsun?",
        "Kira sözleşmesini aç deseydim ne yapardın?",
        "Bugün hava çok güzel, biraz sohbet edelim",
        "Bence dosyaları düzenli tutmak zor oluyor",
        "Kira sözleşmesini sil",
        "Bu dosyanın içeriğini okuyup özetle",
        "Bunu Google Drive'a yükle",
    ],
)
def test_discussion_negation_and_unsupported_operations_do_not_execute(model, text):
    brain, core = runtime(model)
    brain._agent.builtins.find_files({"query": "kira"})
    response = turn(brain, core, text)
    assert not core.calls and not response.executed


def test_numbered_default_then_explicit_browser_are_distinct(model):
    brain, core = runtime(model)
    brain._agent.builtins.find_files({"query": "CV"})
    response = turn(brain, core, "2. olanı açar mısın")
    assert response.executed
    assert core.calls == [{"tool": "open_file", "arguments": {"entry_id": "cv-tr"}}]
    brain._agent.builtins.find_files({"query": "CV"})
    response = turn(brain, core, "Türkçe olan benimki onu Microsoft Edge ile aç")
    assert response.executed
    assert core.calls == [
        {"tool": "resolve_app", "arguments": {"query": "Microsoft Edge"}},
        {
            "tool": "open_file_with_app",
            "arguments": {"entry_id": "cv-tr", "app_id": "fixture-browser"},
        },
    ]


def test_unknown_note_name_scope_and_direct_children(model):
    brain, core = runtime(model)
    turn(brain, core, "Masaüstünde tuttuğum bir not vardı adını hatırlamıyorum, bulalım mı")
    assert brain._files._entries
    assert all(e["location"].startswith("Desktop/") for e in brain._files._entries)
    turn(brain, core, "Alt klasörlere bakma sadece doğrudan masaüstündekileri göster")
    assert {e["entry_id"] for e in brain._files._entries} == {"note"}
    assert all(c["tool"] in {"search_files", "list_directory"} for c in core.calls)


def test_rejection_discussion_and_later_open_keep_identity_separate(model):
    brain, core = runtime(model)
    turn(brain, core, "Masaüstündeki notumu bulalım, ismini hatırlamıyorum")
    turn(brain, core, "New Metin Belgesi olan benimki")
    assert not any(c["tool"].startswith("open_") for c in core.calls)
    turn(brain, core, "Bu bir metin dosyası mı sence?")
    assert not core.calls
    response = turn(brain, core, "O zaman onu aç lütfen")
    assert response.executed
    assert core.calls[-1] == {"tool": "open_file", "arguments": {"entry_id": "note"}}


def test_rejected_results_are_not_reintroduced_by_unknown_name_followup(model):
    brain, core = runtime(model)
    turn(brain, core, "Masaüstündeki üretim notumu bul")
    assert {e["entry_id"] for e in brain._files._entries} == {"nested-note"}
    turn(brain, core, "Hayır bu değil, adını alakasız koymuştum, düz metin dosyasıydı")
    assert "nested-note" not in {e["entry_id"] for e in brain._files._entries}
    assert not any(c["tool"].startswith("open_") for c in core.calls)
    assert all(e["location"].startswith("Desktop/") for e in brain._files._entries)


def test_missing_explicit_folder_cannot_become_global_search(model):
    brain, core = runtime(model)
    turn(brain, core, "Kira sözleşmemi KırmızıArşiv klasörünün içinde ara")
    assert not brain._files._entries
    assert all(
        c["tool"] == "search_files" and c["arguments"].get("kind") == "directory"
        for c in core.calls
    )


class AppCore(Core):
    def __init__(self, ambiguous=False):
        super().__init__()
        self.installed = ambiguous
        self.ambiguous = ambiguous

    def execute_tool(self, tool, args):
        if tool not in {"resolve_app", "open_app", "refresh_app_catalog"}:
            return super().execute_tool(tool, args)
        self.calls.append({"tool": tool, "arguments": dict(args)})
        if tool == "resolve_app":
            if not self.installed:
                raise CoreToolError("application_not_found", "fixture")
            if self.ambiguous and args["query"] == "Studio":
                raise CoreToolError(
                    "application_ambiguous",
                    "fixture",
                    {
                        "candidates": [
                            {"name": "Studio Alpha", "app_id": "alpha"},
                            {"name": "Studio Beta", "app_id": "beta"},
                        ]
                    },
                )
            data = {"app": {"app_id": "beta" if self.ambiguous else "trusted-new-app"}}
        elif tool == "refresh_app_catalog":
            self.installed = True
            data = {"count": 1}
        else:
            data = {"opened": True}
        return ToolResult("fixture", tool, "success", data, None)


def test_new_installation_resumes_only_the_pending_requested_app(model):
    core = AppCore()
    brain = JarvisBrain(core, model)
    turn(brain, core, "Örnek Notlar uygulamasını açar mısın")
    assert [c["tool"] for c in core.calls] == ["resolve_app"]
    query = core.calls[0]["arguments"]["query"]
    response = turn(brain, core, "Ben onu daha yeni yükledim aslında, tekrar bak")
    assert response.executed
    assert core.calls == [
        {"tool": "refresh_app_catalog", "arguments": {}},
        {"tool": "resolve_app", "arguments": {"query": query}},
        {"tool": "open_app", "arguments": {"app_id": "trusted-new-app"}},
    ]


def test_app_ambiguity_uses_private_current_choices(model):
    core = AppCore(ambiguous=True)
    brain = JarvisBrain(core, model)
    turn(brain, core, "Studio uygulamasını aç")
    assert len(brain._agent.builtins.app_choices.pending_candidates()) == 2
    response = turn(brain, core, "İkincisini açar mısın")
    assert response.executed
    assert core.calls == [
        {"tool": "resolve_app", "arguments": {"query": "Studio Beta"}},
        {"tool": "open_app", "arguments": {"app_id": "beta"}},
    ]


@pytest.mark.parametrize(
    "text,authorized",
    [
        ("Bu dosyayı açar mısın", True),
        ("Dosyayı açma", False),
        ("Dosyayı asla açma", False),
        ("Dosyayı açmanı istemiyorum", False),
        ("Dosyayı görüntüleme", False),
        ("Dosyayı gösterme", False),
        ("Dosyayı görüntüler misin", True),
        ("Dosyayı göstermeni istiyorum", True),
        ("Dosyayı açma işlemini başlat", True),
        ("Dosyayı açma işlemini başlatma", False),
        ("Don't open that file", False),
        ("Dosyayı nasıl açarım?", False),
        ("Dosyayı aç deseydim ne yapardın?", False),
        ("Dosyanın içeriğini okuyup özetle", False),
        ("Dosyayı Google Drive'a yükle", False),
        ("Dosyayı sil", False),
        ("Bu dosya benimki", False),
    ],
)
def test_current_action_assessment_rejects_prerequisite_substitution(model, text, authorized):
    model.load()
    proposal = {
        "operation": "Open the requested file or folder now",
        "parameters": {"number": 1},
        "target": {
            "number": 1,
            "name": "kira-sozlesmesi.docx",
            "kind": "file",
            "binding": "unexpired_current_page",
            "candidate_count": 1,
            "application": "",
            "parent": False,
        },
    }
    assessment = model.authorize_action(text, proposal)
    print("assessment", text, assessment, model.events[-1])
    assert assessment.authorized is authorized
