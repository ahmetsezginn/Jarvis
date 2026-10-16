"""Fixed everyday-language corpus. Mocked Core: no personal content, launches or training."""

import os
import re

import pytest
from scripts.evaluation.analyze_file_assistance import FILE_CATEGORIES

from jarvis_brain.intelligence.contract import BrainResponse, IntentName
from jarvis_brain.intelligence.file_session import normalized
from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel
from jarvis_brain.intelligence.runtime import JarvisBrain
from jarvis_brain.ipc.protocol import ToolResult

# Freeze both groups before changing prompts. Evaluate final prompts on the whole corpus.
DEVELOPMENT_REQUESTS = (
    "ben cv mi bilgisayara bir yere koydum şimdi bula mıyorum bana yardımcı olur musun",
    "cv mi bulur musun",
    "cv dosyamı bulur musun dosyayı aramanı istiyorum",
    "dünkü sunumu nereye kaydettiğimi unuttum, bulmama yardım eder misin",
    "iş başvurusu için hazırladığım özgeçmiş ortada yok, bir bakabilir misin",
    "geçen ayki bütçe excelini bulamıyorum, bilgisayarda bulabilir miyiz",
    "bir fatura indirmiştim ama hangi klasörde bilmiyorum, bulabilir misin",
    "tatil fotoğraflarımı bilgisayarda aramama yardımcı olur musun",
)
HELD_OUT_REQUESTS = (
    "ya dün toplantı için bi slayt hazırlamıştım kaydettiğim yeri hatırlamıyorum bulabilir miyiz",
    "hani maaş hesabını tuttuğum excel vardı ya, şimdi hiçbir yerde göremiyorum, bakar mısın",
    "sözleşmenin imzalı pdfini kaydetmiştim, yerini bulamıyorum yardımcı olur musun",
    "kargoyla ilgili makbuzu bilgisayara atmıştım, nereye koyduğumu çıkaramadım bulsana",
    "o bitirme projesi raporu lazım ama klasörlerin içinde kayboldum, dosyayı bulabilir misin",
    "biraz önce indirdiğim sunum dosyasını bulmak istiyorum, nereye gitti acaba",
    "ev kira kontratı vardı bende pdf olarak, bilgisayarda nerede duruyor bulabilir misin",
    "cvyi arıyorum bulamıyom bi yardımcı olsana",
)
NO_ACTION_REQUESTS = (
    "bilgisayarda kaybolan bir dosyayı kendim nasıl bulurum",
    "dosya araması ne demek",
    "cv dosyamı arama, sadece nasıl düzenleyeceğimi konuşalım",
    "sunum dosyamı silme ve açma",
    "bir gün dosyamı kaybedersem ne yapmalıyım",
    "cv nedir, niye istenir",
)
EXPECTED_DEVELOPMENT = (
    "CV-TR.pdf",
    "CV-TR.pdf",
    "CV-TR.pdf",
    "Toplantı-Sunumu.txt",
    "Ahmet-Özgeçmiş.docx",
    "Aylık-Bütçe.xlsx",
    "Fatura.png",
    "Tatil.png",
)
EXPECTED_HELD_OUT = (
    "Toplantı-Slayt.pptx",
    "Maaş.xlsx",
    "İmzalı-Sözleşme.pdf",
    "Kargo-Makbuz.pdf",
    "Bitirme-Projesi-Raporu.docx",
    "Toplantı-Sunumu.pptx",
    "Ev-Kira-Kontratı.pdf",
    "CV-TR.pdf",
)
FIXTURE_NAMES = tuple(dict.fromkeys((*EXPECTED_DEVELOPMENT, *EXPECTED_HELD_OUT, "CV-EN.docx")))


class Core:
    def __init__(self):
        self.calls = []
        self.matches = []

    def execute_tool(self, tool, arguments):
        self.calls.append((tool, arguments))
        assert tool == "search_files", (tool, arguments)
        query = normalized(arguments["query"])
        words = re.findall(r"[a-z0-9]+", query)
        self.matches = [
            name
            for name in FIXTURE_NAMES
            if (
                query == "*"
                or query in normalized(name)
                or (
                    len(words) > 1 and set(words) <= set(re.findall(r"[a-z0-9]+", normalized(name)))
                )
            )
            and (
                not arguments.get("extension")
                or name.lower().endswith("." + arguments["extension"])
            )
            and arguments.get("kind") != "directory"
            and (
                not arguments.get("category")
                or name.lower().endswith(
                    tuple("." + ext for ext in FILE_CATEGORIES[arguments["category"]])
                )
            )
        ]
        data = {
            "entries": [
                {
                    "entry_id": f"trusted-{i}",
                    "name": name,
                    "kind": "file",
                    "location": "private/fixture",
                }
                for i, name in enumerate(self.matches)
            ],
            "total": len(self.matches),
        }
        return ToolResult("id", tool, "success", data, None)


@pytest.fixture(scope="module")
def model():
    if os.environ.get("JARVIS_RUN_NATURAL_FILE_TESTS") != "1":
        pytest.skip("opt-in natural-language GGUF evaluation")
    value = QwenGgufIntentModel()
    yield value
    value.unload()


@pytest.mark.integration
def test_reported_three_turns_recover_from_prior_capability_denials(model):
    core = Core()
    runtime = JarvisBrain(core, model, fast_router_enabled=False)
    for text in DEVELOPMENT_REQUESTS[:3]:
        runtime.reset_context()
        runtime._conversation.observe(
            "cv dosyamı arıyorum",
            BrainResponse(
                IntentName.UNSUPPORTED,
                1,
                "model",
                False,
                "CV dosyasını bulma işlemi desteklenmeyen bir işlemdir.",
            ),
        )
        core.calls.clear()
        response = runtime.handle_text(text)
        print(text, response.intent, core.calls)
        assert [t for t, _ in core.calls] == ["search_files"], (text, response, core.calls)
        assert core.calls[0][1]["query"].casefold() == "cv"


@pytest.mark.integration
def test_everyday_file_goals_across_domains(model):
    failures = []
    for group, examples, expected in [
        ("development", DEVELOPMENT_REQUESTS, EXPECTED_DEVELOPMENT),
        ("held_out", HELD_OUT_REQUESTS, EXPECTED_HELD_OUT),
    ]:
        for text, target in zip(examples, expected, strict=True):
            core = Core()
            runtime = JarvisBrain(core, model, fast_router_enabled=False)
            response = runtime.handle_text(text)
            print(group, text, response.intent, core.calls)
            if (
                [t for t, _ in core.calls] != ["search_files"]
                or target not in core.matches
                or len(core.matches) > 3
                or core.calls[0][1].get("query") in {"", "*"}
            ):
                failures.append((group, text, response.message, core.calls))
    assert not failures, failures


@pytest.mark.integration
def test_explanations_hypotheticals_and_negative_requests_do_not_search(model):
    failures = []
    for text in NO_ACTION_REQUESTS:
        core = Core()
        runtime = JarvisBrain(core, model, fast_router_enabled=False)
        response = runtime.handle_text(text)
        print(text, response.intent, core.calls)
        if core.calls:
            failures.append((text, response.message, core.calls))
    assert not failures, failures


@pytest.mark.integration
def test_repeated_natural_requests_and_new_topic_with_active_results(model):
    core = Core()
    runtime = JarvisBrain(core, model, fast_router_enabled=False)
    for text, target in [
        *zip(DEVELOPMENT_REQUESTS[:3], EXPECTED_DEVELOPMENT[:3], strict=True),
        (DEVELOPMENT_REQUESTS[3], EXPECTED_DEVELOPMENT[3]),
    ]:
        core.calls.clear()
        response = runtime.handle_text(text)
        print("sequential", text, response.intent, core.calls)
        assert [t for t, _ in core.calls] == ["search_files"], (text, response, core.calls)
        assert target in core.matches, (text, response, core.calls)
