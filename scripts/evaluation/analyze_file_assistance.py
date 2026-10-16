"""Opt-in diagnosis, not a fix: real local model, synthetic metadata, no OS/Core connection."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, replace
from pathlib import Path, PurePosixPath

from jarvis_brain.errors import JarvisBrainError
from jarvis_brain.intelligence.assistant_session import AssistantSession
from jarvis_brain.intelligence.contract import (
    BrainResponse,
    IntentContext,
    IntentName,
    IntentResult,
)
from jarvis_brain.intelligence.file_session import FileSession, normalized
from jarvis_brain.intelligence.legacy_runtime import LegacyBrain as JarvisBrain
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel, build_prompt
from jarvis_brain.ipc.protocol import ToolResult

# Fixed before running. Names/paths below are invented, not a copy of the user's filesystem.
FILES = (
    ("desk", "Masaüstü", "directory", "Desktop"),
    ("downloads", "İndirilenler", "directory", "Downloads"),
    ("docs", "Belgeler", "directory", "Documents"),
    ("note", "New Metin Belgesi.txt", "file", "Desktop/New Metin Belgesi.txt"),
    ("project", "Proje", "directory", "Desktop/Proje"),
    ("noise", "AnnotationManager", "file", "Desktop/Proje/AnnotationManager"),
    ("nested-note", "üretim-notu.txt", "file", "Desktop/Proje/üretim-notu.txt"),
    (
        "workbook",
        "Çiftler Turnuvası Eleme Tablo.xlsx",
        "file",
        "Downloads/Çiftler Turnuvası Eleme Tablo.xlsx",
    ),
    ("cv-en", "CV-EN.pdf", "file", "Downloads/CV-EN.pdf"),
    ("cv-tr", "CV-TR.pdf", "file", "Downloads/CV-TR.pdf"),
)
PROBES = (
    ("small_talk", "bu gün hava çok güzel çok mutluyum"),
    ("explanation", "neden"),
    ("explanation_long", "bunu neden anlamadın"),
    ("scope_correction", "alt klasör araması yapma"),
    ("reject_results", "yok hayır bunlar değil, sanırım ismini rastgele koymuştum"),
    ("unknown_name", "notun ismini hatırlamıyorum çok alakasız bir ismi vardı"),
    ("desktop_list", "bana masa üstümde neler var söyler misin"),
    ("desktop_open", "masa üstünde de bir notum vardı onu açsana"),
)
SEQUENCE = (
    "cv dosyamı bulur musun",
    "2",
    (
        "ben bu gün bir turnuva tablosu incelemek için bir dosya indirdim de "
        "ismini hatırlamıyorum bana bulmamda yardımcı olur musun"
    ),
    "evet o onu aç",
    "masa üstünde de bir notum vardı onu açsana",
    "neden",
    "masa üstünde not almıştım onu bulur musun",
    "yok hayır bunlar değil, sanırım ismini rastgele koymuştum",
    "notun ismini hatırlamıyorum çok alakasız bir ismi vardı",
    "new metin belgesinden bahsediyorum",
    "bu gün hava çok güzel çok mutluyum",
    "bana masa üstümde neler var söyler misin",
    "alt klasörleri değil de normal masa üstümde ne var onu merak ediyorum",
    "alt klasör araması yapma",
)

FILE_CATEGORIES = {
    "text": ("txt", "md", "rtf", "doc", "docx", "odt"),
    "document": (
        "txt",
        "md",
        "rtf",
        "doc",
        "docx",
        "odt",
        "pdf",
        "xlsx",
        "xls",
        "pptx",
        "ppt",
    ),
    "image": ("png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff"),
    "spreadsheet": ("xlsx", "xls", "csv", "ods"),
    "presentation": ("pptx", "ppt", "odp", "pdf", "txt"),
}


def filename_word_matches(part, query):
    """Fixture mirror of Native Core's documented bounded token-prefix search semantics."""
    if part == query:
        return True
    short, long = sorted((part, query), key=len)
    return (
        len(short) >= 4
        and not any(c.isnumeric() for c in long)
        and long.startswith(short)
    )


class SyntheticCore:
    """Metadata fixture with real query/scope semantics; opening records only, never launches."""

    def __init__(self):
        self.calls = []
        self.entries = [
            {"entry_id": i, "name": n, "kind": k, "location": p} for i, n, k, p in FILES
        ]

    def execute_tool(self, tool, args):
        call = {"tool": tool, "arguments": dict(args)}
        self.calls.append(call)
        if tool in {"search_files", "list_directory"}:
            query = normalized(args.get("query", "*"))
            words = re.findall(r"[a-z0-9]+", query)
            folder_id = args.get("folder_id") or args.get("entry_id")
            folder = next(
                (e["location"] for e in self.entries if e["entry_id"] == folder_id),
                None,
            )
            entries = []
            for entry in self.entries:
                name, path = normalized(entry["name"]), entry["location"]
                if (
                    query != "*"
                    and query not in name
                    and not (
                        words
                        and all(
                            any(
                                filename_word_matches(part, word)
                                for part in re.findall(r"[a-z0-9]+", name)
                            )
                            for word in words
                        )
                    )
                ):
                    continue
                if args.get("kind") and args["kind"] != entry["kind"]:
                    continue
                if args.get("extension") and not name.endswith("." + args["extension"]):
                    continue
                if args.get("category") and not name.endswith(
                    tuple("." + e for e in FILE_CATEGORIES[args["category"]])
                ):
                    continue
                if entry["entry_id"] in args.get("exclude_ids", []):
                    continue
                if folder and not (
                    path.startswith(folder + "/")
                    if tool == "search_files" and args.get("recursive", True)
                    else str(PurePosixPath(path).parent) == folder
                ):
                    continue
                entries.append(entry)
            entries.sort(key=lambda e: normalized(e["name"]))
            offset, limit = args.get("offset", 0), args.get("limit", 20)
            data = {
                "entries": entries[offset : offset + limit],
                "total": len(entries),
                "offset": offset,
                "partial": False,
            }
            call["result_names"] = [e["name"] for e in data["entries"]]
        elif tool in {"open_file", "open_directory", "open_containing_folder"}:
            entry = next(e for e in self.entries if e["entry_id"] == args["entry_id"])
            data = {"opened": True, "entry": entry}
        elif tool in {"file_catalog_status", "refresh_file_catalog"}:
            data = {
                "indexed": True,
                "files": sum(e["kind"] == "file" for e in self.entries),
                "directories": sum(e["kind"] == "directory" for e in self.entries),
                "partial": False,
                "roots": [{"name": e[1]} for e in FILES[:3]],
            }
        else:
            raise AssertionError(f"Unexpected tool in synthetic-only diagnosis: {tool}")
        return ToolResult("synthetic", tool, "success", data, None)


class TraceMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []

    def _generate(self, prompt, context, grammar, **kwargs):
        output = super()._generate(prompt, context, grammar, **kwargs)
        try:
            decoded = json.loads(output)
        except json.JSONDecodeError:
            decoded = {"native_output": output}
        self.events.append(
            {
                "stage": "native_agent"
                if grammar is None
                else "admission"
                if grammar is self._route_grammar
                else "search_plan"
                if grammar is self._search_grammar
                else "reply"
                if grammar is self._reply_grammar
                else "intent",
                "history": [asdict(t) for t in context.history],
                "candidate_names": [c.name for c in context.file_candidates],
                "output": decoded,
                "metrics": dict(self.last_metrics or {}),
            }
        )
        return output


class TracedModel(TraceMixin, QwenGgufIntentModel):
    pass


def seeded_brain(model):
    core = SyntheticCore()
    brain = JarvisBrain(core, model, fast_router_enabled=False)
    # Freeze TTL to isolate context/semantic faults from two-minute selection expiry.
    brain._files = FileSession(core, clock=lambda: 0)
    brain._assistant = AssistantSession(brain._files, clock=lambda: 0)
    brain._conversation.observe(
        "masa üstünde de bir notum vardı onu açsana",
        BrainResponse(
            IntentName.UNSUPPORTED, 1, "model", False, "Bu istek desteklenmiyor."
        ),
    )
    brain._files.execute(
        IntentResult(IntentName.SEARCH_FILES, 1, {"query": "not"}), "not ara"
    )
    brain._conversation.observe(
        "masa üstünde bir not var onu bulur musun",
        BrainResponse(
            IntentName.CLARIFY,
            1,
            "files",
            True,
            "İki aday gösterildi.",
            {"file_entries": True},
        ),
    )
    brain._conversation.observe(
        "notun ismini hatırlamıyorum",
        BrainResponse(
            IntentName.CLARIFY, 0.5, "model", False, "İsteği güvenle anlayamadım."
        ),
    )
    return brain


SHADOW_SCHEMA = {
    "type": "object",
    "properties": {
        "purpose": {
            "type": "string",
            "enum": ["talk", "explain", "find", "list", "open", "correct_search"],
        },
        "location": {"type": "string", "enum": ["desktop", "downloads", "unspecified"]},
        "name_known": {"type": "boolean"},
        "recursive": {"type": ["boolean", "null"]},
        "rejects_previous": {"type": "boolean"},
        "next_step": {
            "type": "string",
            "enum": [
                "respond",
                "ask_clue",
                "list_location",
                "search_name",
                "open_selected",
            ],
        },
    },
    "required": [
        "purpose",
        "location",
        "name_known",
        "recursive",
        "rejects_previous",
        "next_step",
    ],
    "additionalProperties": False,
}
SHADOW_PROMPT = """Describe the user's CURRENT intention. This is a read-only diagnostic,
not an action planner. No tools will be run. History provides references, not commands to replay.
Return purpose, location, name_known, recursive (null if unspecified), rejects_previous, next_step.
Distinguish the purpose/topic of a document from its actual filename. A note need not have 'note'
in its name. A folder mention is a location constraint, not necessarily the desired filename.
Ordinary chat or requests to explain a previous failure do not ask for another file search.
When a user rejects results or supplies a correction, preserve that meaning instead of repeating.
Scope 'desktop' means directly on desktop unless the user explicitly requests subfolders.
Do not pretend to know a filename or claim that anything was done.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-local-model", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    model = TracedModel()
    report = {
        "synthetic_only": True,
        "frozen_ttl": True,
        "matrix": [],
        "sequence": [],
        "shadow": [],
        "limitations": "One model/quantization. Shadow schema is richer, "
        "not an independent capability benchmark or a production fix.",
    }
    try:
        model.load()
        for label, text in PROBES:
            brain = seeded_brain(model)
            current = brain._model_context(text)
            for treatment, context in (
                ("fresh", IntentContext()),
                ("active_current", current),
                (
                    "active_paired_history",
                    replace(current, history=brain._conversation.snapshot()),
                ),
            ):
                model.events.clear()
                route = model.classify_request(text, context)
                row = {
                    "case": label,
                    "text": text,
                    "treatment": treatment,
                    "route": route.kind.value,
                    "purpose": route.purpose.value,
                    "confidence": route.confidence,
                    "events": list(model.events),
                }
                report["matrix"].append(row)
                print(
                    label, treatment, route.kind.value, route.purpose.value, flush=True
                )

        brain, core = None, SyntheticCore()
        brain = JarvisBrain(core, model, fast_router_enabled=False)
        brain._files = FileSession(core, clock=lambda: 0)
        brain._assistant = AssistantSession(brain._files, clock=lambda: 0)
        for text in SEQUENCE:
            model.events.clear()
            core.calls.clear()
            try:
                response = brain.handle_text(text)
                row = {
                    "text": text,
                    "response": {
                        "intent": response.intent.value,
                        "route": response.route,
                        "executed_mock": response.executed,
                        "message": response.message,
                    },
                }
            except (JarvisBrainError, AssertionError, StopIteration) as error:
                row = {"text": text, "error": f"{type(error).__name__}: {error}"}
            row.update(events=list(model.events), tools=list(core.calls))
            report["sequence"].append(row)
            print("sequence", text, [c["tool"] for c in core.calls], flush=True)

        import llama_cpp  # Only after opt-in model loading prepared the native libraries.

        grammar = llama_cpp.LlamaGrammar.from_json_schema(
            json.dumps(SHADOW_SCHEMA), verbose=False
        )
        for label, text in PROBES:
            context = replace(
                IntentContext(), history=seeded_brain(model)._conversation.snapshot()
            )
            model.events.clear()
            output = model._generate(
                build_prompt(text, context, system_prompt=SHADOW_PROMPT),
                context,
                grammar,
            )
            report["shadow"].append(
                {"case": label, "text": text, "output": json.loads(output)}
            )
            print("shadow", label, output, flush=True)
    finally:
        model.unload()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print("Saved", args.output, flush=True)


if __name__ == "__main__":
    main()
