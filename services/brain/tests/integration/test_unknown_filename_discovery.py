"""Real local model, invented names across domains/languages; no OS effects or contents."""

import os

import pytest
from scripts.evaluation.agent_test_model import TracedReference
from scripts.evaluation.analyze_file_assistance import SyntheticCore

from jarvis_brain.desktop.worker import Session

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_UNKNOWN_NAME_TESTS") != "1":
        pytest.skip("opt-in real model unknown-filename discovery")
    value = TracedReference(gpu_layers=0 if os.environ.get("JARVIS_AGENT_TEST_CPU") == "1" else -1)
    yield value
    value.unload()


class Core(SyntheticCore):
    def __init__(self):
        super().__init__()
        self.entries = [
            {"entry_id": "desk", "name": "Masaüstü", "kind": "directory", "location": "Desktop"},
            {
                "entry_id": "downloads",
                "name": "İndirilenler",
                "kind": "directory",
                "location": "Downloads",
            },
            {
                "entry_id": "text",
                "name": "Q7R2.txt",
                "kind": "file",
                "location": "Desktop/Q7R2.txt",
            },
            {
                "entry_id": "image",
                "name": "DSC_7481.jpg",
                "kind": "file",
                "location": "Desktop/DSC_7481.jpg",
            },
            {
                "entry_id": "sheet",
                "name": "draft-17.xlsx",
                "kind": "file",
                "location": "Desktop/draft-17.xlsx",
            },
            {
                "entry_id": "elsewhere",
                "name": "not-note-photo.xlsx",
                "kind": "file",
                "location": "Downloads/not-note-photo.xlsx",
            },
        ]


def request(model, text, core=None):
    core = core or Core()
    session = Session(core, model)
    model.events.clear()
    result = session.request({"op": "chat", "text": text})
    print(
        text, "=>", result["text"], "cards:", [item["name"] for item in result["items"]], flush=True
    )
    print("calls:", core.calls, "trace:", model.events, flush=True)
    assert all(call["tool"] in {"search_files", "file_catalog_status"} for call in core.calls)
    return session, result


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Masa üstünde bir tane not vardı. Onu bulabilir misin?", "Q7R2.txt"),
        ("There was a note on my Desktop. Could you find it?", "Q7R2.txt"),
        (
            "I saved a photo on the Desktop and forgot its name. Can you help me find it?",
            "DSC_7481.jpg",
        ),
        (
            "Masaüstüne bir hesap tablosu kaydetmiştim, adını hatırlamıyorum. Bulabilir misin?",
            "draft-17.xlsx",
        ),
    ],
)
def test_item_description_does_not_require_literal_filename_words(model, text, expected):
    session, result = request(model, text)
    assert len(result["items"]) == 1
    assert result["items"][0]["name"] == expected
    searches = [
        call["arguments"]
        for call in session.brain._core.calls
        if call["tool"] == "search_files" and call["arguments"].get("kind") != "directory"
    ]
    assert searches and all(call.get("folder_id") == "desk" for call in searches)


def test_an_explicit_exact_name_is_not_silently_replaced_with_another_file(model):
    session, result = request(
        model,
        'Find the file named exactly "missing-report.pdf" on the Desktop. '
        "Keep that exact filename requirement.",
    )
    assert not result["items"]
    searches = [
        call["arguments"]
        for call in session.brain._core.calls
        if call["tool"] == "search_files" and call["arguments"].get("kind") != "directory"
    ]
    # The same mandatory name can be represented as a full query or a stem plus
    # extension. Check the constraint, rather than one spelling of a tool call.
    assert searches
    assert all(
        call.get("query") == "missing-report.pdf"
        or (call.get("query") == "missing-report" and call.get("extension") == "pdf")
        for call in searches
    )
    assert all(call.get("folder_id") == "desk" for call in searches)
    assert any(
        step.get("step") == "find_files" and step["arguments"].get("name_is_constraint") is True
        for step in session.brain._agent.trace
    )


def test_empty_folder_does_not_invent_a_candidate_or_open_anything(model):
    core = Core()
    core.entries = [entry for entry in core.entries if entry["kind"] == "directory"]
    _, result = request(model, "There was a note on my Desktop. Could you find it?", core)
    assert not result["items"] and result["text"].strip()
