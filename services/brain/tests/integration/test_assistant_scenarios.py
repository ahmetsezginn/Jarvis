"""Acceptance conversations with distractors and forbidden operations; opt-in local GGUF only."""

import os

import pytest
from scripts.evaluation.analyze_file_assistance import SyntheticCore, TracedModel

from jarvis_brain.intelligence.runtime import JarvisBrain

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_ASSISTANT_TESTS") != "1":
        pytest.skip("opt-in real local dialogue acceptance")
    value = TracedModel()
    yield value
    value.unload()


def runtime(model):
    core = SyntheticCore()
    core.entries += [
        {
            "entry_id": f"noise-{i}",
            "name": f"random-image-{i}.png",
            "kind": "file",
            "location": f"Documents/Other/random-image-{i}.png",
        }
        for i in range(40)
    ]
    return JarvisBrain(core, model, fast_router_enabled=False), core


def turn(brain, core, text):
    core.calls.clear()
    events = getattr(brain._model, "events", [])
    events.clear()
    response = brain.handle_text(text)
    print(text, response.message, core.calls)
    print("Model trace:", events)
    return response, [c["tool"] for c in core.calls]


def test_search_selection_new_goal_and_chat_transitions(model):
    brain, core = runtime(model)
    response, calls = turn(
        brain, core, "cv mi bilgisayarda bir yere kaydettim bulamıyorum yardımcı olur musun"
    )
    assert calls == ["search_files"]
    assert core.calls[0]["arguments"]["query"] not in {"*", ""}
    assert {e["name"] for e in brain._files._entries} == {"CV-EN.pdf", "CV-TR.pdf"}
    response, calls = turn(brain, core, "2")
    assert calls == ["open_file"] and core.calls[-1]["arguments"]["entry_id"] == "cv-tr"
    response, calls = turn(
        brain,
        core,
        "ben bugün bir turnuva tablosu incelemek için dosya indirdim "
        "ismini hatırlamıyorum bulur musun",
    )
    assert not any(c.startswith("open_") for c in calls)
    assert {e["name"] for e in brain._files._entries} == {"Çiftler Turnuvası Eleme Tablo.xlsx"}
    response, calls = turn(brain, core, "evet o onu aç")
    assert calls == ["open_file"] and core.calls[-1]["arguments"]["entry_id"] == "workbook"
    for text in (
        "neden böyle aradın",
        "bugün hava çok güzel çok mutluyum",
        "sana bir şey soracağım nasılsın",
    ):
        _, calls = turn(brain, core, text)
        assert calls == []


def test_unknown_name_scope_rejection_and_identification_do_not_open(model):
    brain, core = runtime(model)
    response, calls = turn(
        brain, core, "masa üstünde bir notum vardı ismini rastgele koydum onu bulur musun"
    )
    assert not any(c.startswith("open_") for c in calls)
    assert {e["name"] for e in brain._files._entries} == {"New Metin Belgesi.txt"}
    search = core.calls[-1]["arguments"]
    assert search["folder_id"] == "desk" and search["recursive"] is False
    assert search["category"] == "text" and search["query"] == "*"
    _, calls = turn(brain, core, "yok hayır bunlar değil, sanırım ismini rastgele koymuştum")
    assert not any(c.startswith("open_") for c in calls)
    assert not any(e["entry_id"] == "note" for e in brain._files._entries)
    _, calls = turn(brain, core, "notun ismini hatırlamıyorum çok alakasız bir ismi vardı")
    assert not any(c.startswith("open_") for c in calls)
    _, calls = turn(brain, core, "new metin belgesinden bahsediyorum")
    assert not any(c.startswith("open_") for c in calls)
    assert {e["name"] for e in brain._files._entries} == {"New Metin Belgesi.txt"}
    _, calls = turn(brain, core, "bunu neden anlamadın")
    assert calls == []


def test_direct_desktop_listing_and_scope_correction(model):
    brain, core = runtime(model)
    for text in (
        "bana masa üstümde neler var söyler misin",
        "alt klasörleri değil de normal masa üstümde ne var onu merak ediyorum",
        "alt klasör araması yapma",
    ):
        _, calls = turn(brain, core, text)
        assert "list_directory" in calls
        assert not any(c.startswith("open_") for c in calls)
        assert {e["name"] for e in brain._files._entries} == {"New Metin Belgesi.txt", "Proje"}
        assert core.calls[-1]["arguments"]["entry_id"] == "desk"


def test_missing_clue_question_answer_and_cancellation(model):
    brain, core = runtime(model)
    response, calls = turn(brain, core, "bir notumu kaybettim ismini hiç hatırlamıyorum")
    assert not calls and "?" in response.message
    _, calls = turn(brain, core, "masaüstüne kaydetmiştim")
    assert {e["name"] for e in brain._files._entries} == {"New Metin Belgesi.txt"}
    turn(brain, core, "iptal")
    response, calls = turn(brain, core, "onu aç")
    assert not calls and not response.executed


@pytest.mark.parametrize(
    "text",
    [
        "Steam'i açma",
        "cv dosyamı arama sadece nasıl düzenleyeceğimi konuşalım",
        "bir gün dosyamı kaybedersem ne yapmalıyım",
        "dosyamı kendim nasıl bulurum",
        "bugün çok mutluyum",
        "az önce neden bu sonuçları gösterdin",
        "dosya açabilir misin",
        "uygulama açabilir misin",
    ],
)
def test_non_action_with_active_file_goal(model, text):
    brain, core = runtime(model)
    turn(brain, core, "masaüstündeki notları bulur musun")
    _, calls = turn(brain, core, text)
    assert calls == []


@pytest.mark.parametrize(
    "text",
    [
        "bugün çok mutluyum",
        "dosyamı kendim nasıl bulurum",
        "neden klasörü soruyorsun",
        "arama yapma vazgeçtim",
    ],
)
def test_pending_question_does_not_authorize_unrelated_actions(model, text):
    brain, core = runtime(model)
    _, calls = turn(brain, core, "bir notumu kaybettim ismini hiç hatırlamıyorum")
    assert not calls
    _, calls = turn(brain, core, text)
    assert calls == []


@pytest.mark.parametrize(
    "text",
    [
        "Türkçe olan benim dosyam",
        "ikinci olan benim",
        "bu dosyadan bahsediyorum",
        "2. dosyayı sil",
        "cv dosyamın içeriğini oku",
        "bu dosyayı internete yükle",
    ],
)
def test_identification_and_unavailable_operations_never_open_instead(model, text):
    brain, core = runtime(model)
    turn(brain, core, "cv dosyalarımı bul")
    assert len(brain._files._entries) == 2
    _, calls = turn(brain, core, text)
    assert calls == []
