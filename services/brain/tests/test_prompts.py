from jarvis_brain.intelligence.prompts import build_non_thinking_prompt


def test_prompt_uses_qwen3_non_thinking_assistant_prefix_and_small_contract() -> None:
    prompt = build_non_thinking_prompt("Google Chrome'u aç")
    assert prompt.endswith("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    assert "app_id" in prompt
    assert "Never output app_id" in prompt
    assert "run_shell" not in prompt
