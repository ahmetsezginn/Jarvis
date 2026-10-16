import pytest

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.contract import IntentName, IntentResult
from jarvis_brain.intelligence.file_reference import numbered_reference
from jarvis_brain.intelligence.file_session import FileSession
from jarvis_brain.intelligence.legacy_runtime import LegacyBrain as JarvisBrain
from jarvis_brain.intelligence.models.fake import FakeIntentModel
from jarvis_brain.intelligence.parser import parse_model_output
from jarvis_brain.ipc.protocol import ToolResult


class Core:
    def __init__(self):
        self.calls = []
        self.entries = [
            {"entry_id": f"trusted-{i}", "name": name, "kind": "file", "location": f"private/{i}"}
            for i, name in enumerate(
                [
                    "CV-EN.pdf",
                    "CV-TR.pdf",
                    "CV.pdf",
                    "Other.pdf",
                    "CV-tr.pdf",
                    "Resume.pdf",
                    "Photo_TR.pdf",
                ]
            )
        ]

    def execute_tool(self, tool, args):
        self.calls.append((tool, args))
        if tool == "search_files":
            data = {"entries": self.entries, "total": len(self.entries)}
        elif tool == "resolve_app":
            data = {"resolved": True, "app": {"app_id": "trusted-browser"}}
        else:
            data = {"opened": True, "entry": {"name": "parent"}}
        return ToolResult("id", tool, "success", data, None)


def selected(number=2, action="open", application=""):
    return IntentResult(
        IntentName.SELECT_FILE, 1, {"number": number, "action": action, "application": application}
    )


def runtime_with_page(core, result):
    runtime = JarvisBrain(core, FakeIntentModel(result))
    runtime._files.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "CV bul")
    core.calls.clear()
    return runtime


@pytest.mark.parametrize(
    "text, number",
    [
        ("2. olanı açar mısın", 2),
        ("7) aç", 7),
        ("3 numaralı dosyayı aç", 3),
        ("4 olanı aç", 4),
        ("2", 2),
        ("1. sonucu Chrome ile aç", 1),
    ],
)
def test_list_notation_is_a_reference_not_an_action(text, number):
    assert numbered_reference(text) == number


@pytest.mark.parametrize(
    "text",
    [
        "2 tane resim bul",
        "2.pdf dosyasını aç",
        "2026 raporunu bul",
        "adı 2 olan dosyaları bul",
        "resim 2 bul",
    ],
)
def test_file_names_and_quantities_are_not_result_addresses(text):
    assert numbered_reference(text) is None


@pytest.mark.parametrize("number", range(1, 8))
def test_display_number_binds_exact_current_page_entry_without_search(number):
    core = Core()
    runtime = runtime_with_page(core, selected(number))
    response = runtime.handle_text(f"{number}. olanı açar mısın")
    assert response.executed
    assert core.calls == [("open_file", {"entry_id": f"trusted-{number - 1}"})]


def test_wrong_search_prediction_cannot_replace_the_cv_page_with_images():
    core = Core()
    runtime = runtime_with_page(core, IntentResult(IntentName.SEARCH_FILES, 1, {"query": "2"}))
    original = runtime._files._entries
    response = runtime.handle_text("2. olanı açar mısın")
    assert not response.executed and not core.calls
    assert runtime._files._entries == original


def test_model_cannot_redirect_explicit_number_to_another_row():
    core = Core()
    runtime = runtime_with_page(core, selected(1))
    assert not runtime.handle_text("2. olanı açar mısın").executed
    assert not core.calls


@pytest.mark.parametrize("state", ["empty", "expired", "reset", "out_of_range"])
def test_missing_expired_or_invalid_page_reference_never_searches(state):
    core = Core()
    runtime = runtime_with_page(core, selected())
    if state == "expired":
        runtime._files._expires = 0
    elif state in {"empty", "reset"}:
        runtime.reset_context()
    response = runtime.handle_text(
        "8. olanı açar mısın" if state == "out_of_range" else "2. olanı açar mısın"
    )
    assert not response.executed and not core.calls


def test_application_selection_does_not_change_target_or_leak_to_default_open():
    core = Core()
    runtime = runtime_with_page(core, selected(2, application="Microsoft Edge"))
    assert runtime.handle_text("2. dosyayı Edge ile aç").executed
    assert core.calls == [
        ("resolve_app", {"query": "Microsoft Edge"}),
        ("open_file_with_app", {"entry_id": "trusted-1", "app_id": "trusted-browser"}),
    ]
    runtime = runtime_with_page(core, selected(2))
    assert runtime.handle_text("2. dosyayı normal aç").executed
    assert core.calls == [("open_file", {"entry_id": "trusted-1"})]


def test_skipped_model_names_do_not_renumber_real_display_positions():
    core = Core()
    core.entries[0]["name"] = "a" * 257
    runtime = runtime_with_page(core, selected(2))
    candidates = runtime._files.model_candidates()
    assert candidates[0].number == 2
    assert runtime.handle_text("2. olanı açar mısın").executed
    assert core.calls == [("open_file", {"entry_id": "trusted-1"})]


@pytest.mark.parametrize(
    "arguments",
    [
        {"number": True, "action": "open", "application": ""},
        {"number": 0, "action": "open", "application": ""},
        {"number": 21, "action": "open", "application": ""},
        {"number": 2, "action": "run_shell", "application": ""},
        {"number": 2, "action": "open", "application": "cmd.exe"},
        {"number": 2, "action": "open", "application": "", "entry_id": "invented"},
        {"number": 2, "action": "parent", "application": "Chrome"},
    ],
)
def test_reference_schema_cannot_supply_paths_ids_or_invalid_operations(arguments):
    import json

    with pytest.raises(ModelOutputInvalid):
        parse_model_output(
            json.dumps({"intent": "select_file", "confidence": 1, "arguments": arguments})
        )


def test_new_filename_search_remains_separate_from_page_selection():
    core = Core()
    runtime = runtime_with_page(
        core,
        IntentResult(
            IntentName.SEARCH_FILES,
            1,
            {"query": "2", "kind": "file", "extension": "png", "sort": "name"},
        ),
    )
    runtime.handle_text("adı 2 olan resimleri bul")
    assert core.calls[0][0] == "search_files"


def test_selection_operation_routes_without_resolving_a_new_name():
    core = Core()
    runtime = runtime_with_page(core, selected(2, action="parent"))
    assert runtime.handle_text("2. dosyanın bulunduğu klasörü aç").executed
    assert core.calls == [("open_containing_folder", {"entry_id": "trusted-1"})]


def test_page_change_rebinds_positions_to_new_current_page():
    core = Core()
    session = FileSession(core)
    session.execute(IntentResult(IntentName.SEARCH_FILES, 1, {"query": "cv"}), "bul")
    core.entries = [{**e, "entry_id": "next-" + e["entry_id"]} for e in core.entries]
    session._observe({"entries": core.entries, "total": 30, "offset": 20}, IntentName.SEARCH_FILES)
    core.calls.clear()
    assert session.execute(selected(2), "2. olanı aç").executed
    assert core.calls == [("open_file", {"entry_id": "next-trusted-1"})]


@pytest.mark.parametrize("text", ["-1. olanı aç", "0. olanı aç"])
def test_nonpositive_references_never_open_another_row_or_search(text):
    core = Core()
    runtime = runtime_with_page(core, selected(1))
    assert not runtime.handle_text(text).executed
    assert core.calls == []


def test_low_confidence_selection_does_not_consume_the_page():
    core = Core()
    runtime = runtime_with_page(
        core, IntentResult(IntentName.SELECT_FILE, 0.1, selected().arguments)
    )
    assert not runtime.handle_text("2. olanı açar mısın").executed
    assert core.calls == [] and runtime._files.accepts_number(2)


def test_core_rejection_consumes_reference_without_search_or_retry():
    from jarvis_brain.errors import CoreToolError

    core = Core()
    runtime = runtime_with_page(core, selected(2))

    def rejected(tool, arguments):
        core.calls.append((tool, arguments))
        raise CoreToolError("invalid_arguments", "stale catalog entry")

    core.execute_tool = rejected
    assert not runtime.handle_text("2. olanı açar mısın").executed
    assert core.calls == [("open_file", {"entry_id": "trusted-1"})]
    core.calls.clear()
    assert not runtime.handle_text("2. olanı açar mısın").executed
    assert not core.calls
