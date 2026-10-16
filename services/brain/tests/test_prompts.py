from jarvis_brain.intelligence.prompts import build_non_thinking_prompt


def test_prompt_uses_qwen3_non_thinking_assistant_prefix_and_small_contract() -> None:
    prompt = build_non_thinking_prompt("Google Chrome'u aç")
    assert prompt.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert "app_id" in prompt
    assert "Never output app_id" in prompt
    assert "run_shell" not in prompt


def test_gguf_file_admission_guidance_does_not_change_compact_onnx_route_prompt():
    from jarvis_brain.intelligence.request_routing import GGUF_ROUTE_PROMPT, ROUTE_PROMPT

    assert "file_candidates" in GGUF_ROUTE_PROMPT
    assert "file_candidates" not in ROUTE_PROMPT


def test_conversation_current_payload_retains_metadata_without_repeating_history():
    import json

    from jarvis_brain.intelligence.contract import ConversationTurn, FileCandidate, IntentContext
    from jarvis_brain.intelligence.prompts import build_conversation_messages

    context = IntentContext(
        history=(ConversationTurn("garanti belgesini bul", "İki sonuç bulundu."),),
        file_candidates=(FileCandidate("urun-garanti.pdf", "file", 2),),
        pending_file_question="Hangisi olabilir?",
    )
    prompt = build_conversation_messages("sence hangisi", context)
    final = prompt.rsplit("<|im_start|>user\n", 1)[1].split("<|im_end|>", 1)[0]
    payload = json.loads(final)
    assert payload["file_candidates"] == [{"number": 2, "name": "urun-garanti.pdf", "kind": "file"}]
    assert payload["pending_file_question"] == "Hangisi olabilir?"
    assert "recent_conversation" not in payload
    assert prompt.count("garanti belgesini bul") == 1
