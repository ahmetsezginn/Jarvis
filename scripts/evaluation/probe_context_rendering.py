"""Controlled prompt-rendering ablation, same pinned GGUF and schemas; no tools executed."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from jarvis_brain.intelligence.contract import (
    ConversationTurn,
    FileCandidate,
    IntentContext,
)
from jarvis_brain.intelligence.models.qwen_gguf import build_prompt
from jarvis_brain.intelligence.prompts import build_user_payload
from jarvis_brain.intelligence.request_routing import GGUF_ROUTE_PROMPT

from scripts.evaluation.analyze_file_assistance import (
    FILES,
    PROBES,
    SHADOW_PROMPT,
    SHADOW_SCHEMA,
    TracedModel,
    seeded_brain,
)


def render(text, context, system, treatment):
    if treatment == "current_first":
        return build_prompt(text, context, system_prompt=system)
    payload = json.loads(build_user_payload(text, context))
    current = payload.pop("user_input")
    if treatment == "ordered_messages":
        payload.pop("recent_conversation", None)
        history = "".join(
            "<|im_start|>user\n"
            + json.dumps({"user_input": t.user}, ensure_ascii=False)
            + "<|im_end|>\n<|im_start|>assistant\n"
            + json.dumps({"message": t.assistant}, ensure_ascii=False)
            + "<|im_end|>\n"
            for t in context.history
        )
    else:
        history = ""
    payload["user_input"] = current
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        + history
        + "<|im_start|>user\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + "<|im_end|>\n<|im_start|>assistant\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local-model", action="store_true", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = json.loads(args.input.read_text(encoding="utf-8"))
    kinds = {name: kind for _, name, kind, _ in FILES}
    model = TracedModel()
    report = {
        "same_model_and_grammar": True,
        "production_changes": False,
        "routing": [],
        "shadow": [],
    }
    try:
        model.load()
        for row in prior["sequence"]:
            if row["text"] not in {
                "neden",
                "bu gün hava çok güzel çok mutluyum",
                "masa üstünde de bir notum vardı onu açsana",
                "bana masa üstümde neler var söyler misin",
                "alt klasör araması yapma",
            }:
                continue
            event = next(e for e in row["events"] if e["stage"] == "admission")
            context = IntentContext(
                history=tuple(ConversationTurn(**t) for t in event["history"]),
                file_candidates=tuple(
                    FileCandidate(n, kinds[n], i)
                    for i, n in enumerate(event["candidate_names"], 1)
                ),
            )
            for treatment in ("current_first", "current_last", "ordered_messages"):
                prompt = render(row["text"], context, GGUF_ROUTE_PROMPT, treatment)
                output = model._generate(prompt, context, model._route_grammar)
                result = {
                    "text": row["text"],
                    "rendering": treatment,
                    "output": json.loads(output),
                }
                report["routing"].append(result)
                print("routing", row["text"], treatment, output, flush=True)

        import llama_cpp

        grammar = llama_cpp.LlamaGrammar.from_json_schema(
            json.dumps(SHADOW_SCHEMA), verbose=False
        )
        for label, text in PROBES:
            if label not in {
                "small_talk",
                "explanation",
                "scope_correction",
                "desktop_list",
                "unknown_name",
            }:
                continue
            context = replace(
                IntentContext(), history=seeded_brain(model)._conversation.snapshot()
            )
            for treatment in ("current_first", "current_last", "ordered_messages"):
                output = model._generate(
                    render(text, context, SHADOW_PROMPT, treatment), context, grammar
                )
                report["shadow"].append(
                    {
                        "case": label,
                        "rendering": treatment,
                        "output": json.loads(output),
                    }
                )
                print("shadow", label, treatment, output, flush=True)
    finally:
        model.unload()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()
