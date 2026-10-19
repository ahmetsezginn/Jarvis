"""Real-model, cross-domain behavioral acceptance. Invented metadata; no OS launches.

English-primary acceptance; Turkish filenames remain unchanged.
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
    ("lease", "rental-agreement.docx"),
    ("statistics", "statistics-class-notes.txt"),
    ("garden", "garden-plan.png"),
    ("budget", "family-budget.xlsx"),
    ("recipe", "lentil-soup-recipe.txt"),
    ("recording", "piano-recording.wav"),
    ("photo", "graduation-photo.jpg"),
    ("presentation", "marketing-presentation.txt"),
)
REPORTED_DOCUMENTS = (
    ("certificate", "technical-certificate.pdf"),
    ("warranty", "refrigerator-warranty.pdf"),
    ("invoice", "car-service-invoice.pdf"),
    ("flight", "flight-ticket.pdf"),
)


class Core(SyntheticCore):
    def __init__(self):
        super().__init__()
        for entry in self.entries:
            if entry["entry_id"] in {"desk", "downloads", "docs"}:
                entry["name"] = entry["location"]
            if entry["entry_id"] == "nested-note":
                entry["name"] = "production-note.txt"
                entry["location"] = "Desktop/Proje/production-note.txt"
        self.entries.extend(
            {"entry_id": id_, "name": name, "kind": "file", "location": f"Downloads/{name}"}
            for id_, name in DOCUMENTS
        )
        self.entries.extend(
            {
                "entry_id": f"noise-{i}",
                "name": f"unrelated-document-{i}.pdf",
                "kind": "file",
                "location": f"Documents/unrelated-document-{i}.pdf",
            }
            for i in range(25)
        )

    def execute_tool(self, tool, args):
        if tool in {"file_catalog_status", "refresh_file_catalog"}:
            result = super().execute_tool(tool, args)
            result.data["roots"] = [
                {"name": name} for name in ("Desktop", "Downloads", "Documents")
            ]
            return result
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
    if os.environ.get("JARVIS_RUN_ENGLISH_AGENT_TESTS") != "1":
        pytest.skip("opt-in real model agent acceptance")
    value = test_model(os.environ.get("JARVIS_AGENT_TEST_PROFILE", "qwen35"))
    yield value
    value.unload()


def runtime(model):
    core = Core()
    return JarvisBrain(core, model), core


def turn(brain, core, text):
    core.calls.clear()
    brain._model.events.clear()
    try:
        response = brain.handle_text(text)
    except Exception:
        print("failed request", text, "Core calls", core.calls)
        print("rejected model trace", brain._model.events)
        raise
    print(text, "=>", response.message, core.calls)
    print("model trace", brain._model.events)
    return response


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "I saved the rental agreement with my landlord somewhere but cannot find it. "
            "Can you help?",
            "lease",
        ),
        ("Where did my statistics class notes go? Help me find them.", "statistics"),
        ("I seem to have lost my garden plan on the computer. Could you take a look?", "garden"),
        ("I am looking for the spreadsheet I made for our family budget.", "budget"),
        ("I wrote down a lentil soup recipe. Could you find which file it was in?", "recipe"),
        ("I cannot find my piano recording on this computer. Can you help?", "recording"),
        ("Could you find my graduation photo?", "photo"),
        (
            "I am looking for my marketing presentation, but I do not remember its extension.",
            "presentation",
        ),
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
    response = turn(brain, core, "Yes, that is the one I was looking for. Could you open it?")
    assert response.executed
    assert core.calls == [{"tool": "open_file", "arguments": {"entry_id": id_}}]


@pytest.mark.parametrize(
    "text",
    [
        "Don't open Steam",
        "How would I open this file? Explain the steps.",
        "Can you find my files? What are your capabilities?",
        "What would you do if I asked you to open my rental agreement?",
        "The weather is lovely today. Let's chat.",
        "I think keeping files organized is difficult.",
        "Delete the rental agreement.",
        "Read and summarize the contents of this file.",
        "Upload this to Google Drive.",
    ],
)
def test_discussion_negation_and_unsupported_operations_do_not_execute(model, text):
    brain, core = runtime(model)
    brain._agent.builtins.find_files({"query": "rental"})
    response = turn(brain, core, text)
    assert not core.calls and not response.executed


def test_numbered_default_then_explicit_browser_are_distinct(model):
    brain, core = runtime(model)
    brain._agent.builtins.find_files({"query": "CV"})
    response = turn(brain, core, "Could you open the second one?")
    assert response.executed
    assert core.calls == [{"tool": "open_file", "arguments": {"entry_id": "cv-tr"}}]
    brain._agent.builtins.find_files({"query": "CV"})
    response = turn(brain, core, "The Turkish one is mine. Open it with Microsoft Edge.")
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
    turn(
        brain,
        core,
        "I had a note on my Desktop but I cannot remember its name. Can you help me find it?",
    )
    assert brain._files._entries
    assert all(e["location"].startswith("Desktop/") for e in brain._files._entries)
    turn(brain, core, "Don't look in subfolders. Show only files directly on my Desktop.")
    assert {e["entry_id"] for e in brain._files._entries} == {"note"}
    assert all(c["tool"] in {"search_files", "list_directory"} for c in core.calls)


def test_rejection_discussion_and_later_open_keep_identity_separate(model):
    brain, core = runtime(model)
    turn(brain, core, "Let's find my note on the Desktop. I don't remember its filename.")
    turn(brain, core, "The one named New Metin Belgesi is mine.")
    assert not any(c["tool"].startswith("open_") for c in core.calls)
    turn(brain, core, "Does that look like a text file to you?")
    assert not core.calls
    response = turn(brain, core, "Then open that one, please.")
    assert response.executed
    assert core.calls[-1] == {"tool": "open_file", "arguments": {"entry_id": "note"}}


def test_rejected_results_are_not_reintroduced_by_unknown_name_followup(model):
    brain, core = runtime(model)
    turn(brain, core, "Find my production note on the Desktop.")
    assert {e["entry_id"] for e in brain._files._entries} == {"nested-note"}
    turn(brain, core, "No, not this one. I gave it an unrelated name. It was a plain text file.")
    assert "nested-note" not in {e["entry_id"] for e in brain._files._entries}
    assert not any(c["tool"].startswith("open_") for c in core.calls)
    assert all(e["location"].startswith("Desktop/") for e in brain._files._entries)


def test_missing_explicit_folder_cannot_become_global_search(model):
    brain, core = runtime(model)
    turn(brain, core, "Look for my rental agreement inside the RedArchive folder.")
    assert not brain._files._entries
    assert all(
        c["tool"] == "file_catalog_status"
        or (c["tool"] == "search_files" and c["arguments"].get("kind") == "directory")
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
    turn(brain, core, "Could you open the Sample Notes app?")
    assert [c["tool"] for c in core.calls] == ["resolve_app"]
    query = core.calls[0]["arguments"]["query"]
    response = turn(brain, core, "Actually, I only just installed it. Take another look.")
    assert response.executed
    assert core.calls == [
        {"tool": "refresh_app_catalog", "arguments": {}},
        {"tool": "resolve_app", "arguments": {"query": query}},
        {"tool": "open_app", "arguments": {"app_id": "trusted-new-app"}},
    ]


def test_app_ambiguity_uses_private_current_choices(model):
    core = AppCore(ambiguous=True)
    brain = JarvisBrain(core, model)
    turn(brain, core, "Open the Studio app.")
    assert len(brain._agent.builtins.app_choices.pending_candidates()) == 2
    response = turn(brain, core, "Could you open the second one?")
    assert response.executed
    assert core.calls == [
        {"tool": "resolve_app", "arguments": {"query": "Studio Beta"}},
        {"tool": "open_app", "arguments": {"app_id": "beta"}},
    ]


@pytest.mark.parametrize(
    "text,authorized",
    [
        ("Could you open this file?", True),
        ("Do not open the file.", False),
        ("Never open the file.", False),
        ("I don't want you to open the file.", False),
        ("Do not display the file.", False),
        ("Do not show the file.", False),
        ("Could you display the file?", True),
        ("I want you to show the file.", True),
        ("Start opening the file.", True),
        ("Do not start opening the file.", False),
        ("Don't open that file", False),
        ("How do I open the file?", False),
        ("What would you do if I said open the file?", False),
        ("Read the file contents and summarize them.", False),
        ("Upload the file to Google Drive.", False),
        ("Delete the file.", False),
        ("This file is mine.", False),
    ],
)
def test_current_action_assessment_rejects_prerequisite_substitution(model, text, authorized):
    model.load()
    proposal = {
        "operation": "Open the requested file or folder now",
        "parameters": {"number": 1},
        "target": {
            "number": 1,
            "name": "rental-agreement.docx",
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


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I cannot find my technical certificate. Could you help me?", "certificate"),
        ("I cannot find my tecnical certficate. Can you help?", "certificate"),
        ("I saved the refrigerator warranty somewhere and now I cannot find it.", "warranty"),
        ("The car service invoice was somewhere on this computer. Help me find it.", "invoice"),
        ("I put my flight ticket somewhere. Could you look for it?", "flight"),
    ],
)
def test_reported_discovery_cases_in_english(model, text, expected):
    brain, core = reported_runtime(model)
    turn(brain, core, text)
    assert {e["entry_id"] for e in brain._files._entries} == {expected}
    assert core.calls and all(c["tool"] == "search_files" for c in core.calls)
    assert all(c["arguments"]["query"] not in {"*", ""} for c in core.calls)


def test_reported_pronoun_open_in_english(model):
    brain, core = reported_runtime(model)
    turn(brain, core, "I cannot find my technical certificate. Could you help me?")
    assert {e["entry_id"] for e in brain._files._entries} == {"certificate"}
    response = turn(brain, core, "I want you to open it.")
    assert response.executed
    assert core.calls == [{"tool": "open_file", "arguments": {"entry_id": "certificate"}}]


def test_reported_metadata_discussion_in_english(model):
    brain, core = reported_runtime(model)
    turn(brain, core, "Find the refrigerator warranty.")
    assert {e["entry_id"] for e in brain._files._entries} == {"warranty"}
    response = turn(brain, core, "From its name, do you think that might be the one I need?")
    assert not core.calls and not response.executed
    assert "warranty" in response.message.casefold()
    assert {e["entry_id"] for e in brain._files._entries} == {"warranty"}


def reported_runtime(model):
    brain, core = runtime(model)
    core.entries.extend(
        {"entry_id": id_, "name": name, "kind": "file", "location": f"Downloads/{name}"}
        for id_, name in REPORTED_DOCUMENTS
    )
    return brain, core


@pytest.mark.parametrize(
    "text,allowed",
    [
        ("Could you open the file?", False),
        ("Could you open the file with WriterPro?", True),
    ],
)
def test_current_action_assessment_distinguishes_requested_and_inferred_app(model, text, allowed):
    assessment = model.authorize_action(
        text,
        {
            "operation": "Open the selected file",
            "parameters": {"number": 1, "application": "WriterPro"},
            "target": {
                "number": 1,
                "name": "draft.odt",
                "candidate_count": 1,
                "binding": "unexpired_current_results",
            },
        },
    )
    print("App preference assessment:", text, assessment, flush=True)
    assert assessment.authorized is allowed
