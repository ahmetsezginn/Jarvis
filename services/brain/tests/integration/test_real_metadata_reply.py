"""Focused reply-component check, not end-to-end planner acceptance. No Core/OS calls."""

import os

import pytest

from jarvis_brain.intelligence.contract import ConversationTurn, FileCandidate, IntentContext
from jarvis_brain.intelligence.file_session import normalized
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_GGUF_TESTS") != "1":
        pytest.skip("opt-in real GGUF reply component")
    value = QwenGgufIntentModel()
    value.load()
    yield value
    value.unload()


@pytest.mark.parametrize(
    "goal,target,distractor",
    [
        ("buzdolabının garanti belgesini arıyorum", "buzdolabi-garanti.pdf", "tatil-bileti.pdf"),
        ("arabanın servis faturasını arıyorum", "oto-servis-fatura.pdf", "ev-kira-sozlesmesi.pdf"),
        ("okulun ders programını arıyorum", "ders-programi.xlsx", "restoran-menu.pdf"),
    ],
)
def test_reply_can_recommend_from_verified_names_without_claiming_content(
    model, goal, target, distractor
):
    context = IntentContext(
        history=(ConversationTurn(goal, "İki dosya bulundu; içeriklerini okumadım."),),
        file_candidates=(
            FileCandidate(distractor, "file", 1),
            FileCandidate(target, "file", 2),
        ),
    )
    reply = model.respond(
        "Dosya adlarına bakarak hangisi olabilir sence? Bir öneride bulun.", context
    )
    print(goal, "=>", reply)
    assert normalized(target) in normalized(reply)
    assert "yetkim yok" not in reply.casefold()
    assert "okudum" not in reply.casefold()


def test_reply_does_not_invent_a_match_when_metadata_is_missing(model):
    reply = model.respond("Az önceki sonuçlardan hangisi benim belgem olabilir?", IntentContext())
    print("no metadata =>", reply)
    assert not any(suffix in reply.casefold() for suffix in (".pdf", ".xlsx", ".docx"))
