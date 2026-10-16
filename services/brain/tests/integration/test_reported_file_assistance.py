"""Unresolved natural dialogue regressions. Real GGUF; synthetic metadata; no OS calls.

These assertions intentionally describe the desired behavior, including known failures.
Do not weaken them to tool-call/target-inclusion checks or mark failures as accepted.
"""

import os

import pytest
from scripts.evaluation.agent_test_model import test_model
from scripts.evaluation.analyze_file_assistance import SyntheticCore

from jarvis_brain.intelligence.runtime import JarvisBrain

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_ASSISTANT_TESTS") != "1":
        pytest.skip("opt-in real GGUF reported dialogue regressions")
    value = test_model(os.environ.get("JARVIS_AGENT_TEST_PROFILE", "qwen3-4b"))
    yield value
    value.unload()


def runtime(model):
    core = SyntheticCore()
    core.entries.extend(
        {"entry_id": id_, "name": name, "kind": "file", "location": f"Downloads/{name}"}
        for id_, name in (
            ("certificate", "teknik-sertifika.pdf"),
            ("warranty", "buzdolabi-garanti.pdf"),
            ("invoice", "oto-servis-fatura.pdf"),
            ("flight", "ucak-bileti.pdf"),
        )
    )
    core.entries.extend(
        {
            "entry_id": f"noise-{i}",
            "name": f"diger-belge-{i:02d}.pdf",
            "kind": "file",
            "location": f"Downloads/diger-belge-{i:02d}.pdf",
        }
        for i in range(40)
    )
    return JarvisBrain(core, model, fast_router_enabled=False), core


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
        ("sertifikamı bulamıyorum da bana yardımcı olur musun", "certificate"),
        ("ben certificamı bulamıyorum da yardımcı olur musun", "certificate"),
        ("buzdolabının garanti belgesini kaydetmiştim şimdi bulamıyorum", "warranty"),
        ("arabamın servis faturası bilgisayarda bir yerdeydi bulamıyorum", "invoice"),
        ("uçak biletini bir yere atmışım bulsana", "flight"),
    ],
    ids=["certificate", "typo", "warranty", "invoice", "ticket"],
)
def test_lost_document_finds_precise_candidate_without_opening(model, text, expected):
    brain, core = runtime(model)
    turn(brain, core, text)
    # Discovery may inspect catalog scope; require the right result and no launch/mutation,
    # rather than prescribing the old planner's exact internal call sequence.
    assert core.calls and all(
        call["tool"] in {"search_files", "file_catalog_status"} for call in core.calls
    )
    assert {entry["entry_id"] for entry in brain._files._entries} == {expected}
    assert all(
        call["arguments"]["query"] not in {"*", ""}
        for call in core.calls
        if call["tool"] == "search_files"
    )


def test_single_found_document_can_be_opened_by_pronoun(model):
    brain, core = runtime(model)
    turn(brain, core, "sertifikamı bulamıyorum da bana yardımcı olur musun")
    assert {entry["entry_id"] for entry in brain._files._entries} == {"certificate"}
    response = turn(brain, core, "onu açmanı istiyorum")
    assert response.executed
    assert core.calls == [{"tool": "open_file", "arguments": {"entry_id": "certificate"}}]


def test_metadata_discussion_does_not_discard_found_page(model):
    brain, core = runtime(model)
    turn(brain, core, "buzdolabının garanti belgesini bul")
    assert {entry["entry_id"] for entry in brain._files._entries} == {"warranty"}
    response = turn(brain, core, "Dosya adına bakarak bu aradığım olabilir mi sence?")
    assert not core.calls and not response.executed
    assert "garanti" in response.message.casefold()
    assert {entry["entry_id"] for entry in brain._files._entries} == {"warranty"}
