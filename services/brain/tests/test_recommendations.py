"""One-at-a-time suggestions across domains, with private stable identities and no effects."""

import pytest
from scripts.evaluation.analyze_file_assistance import SyntheticCore
from services.brain.tests.test_agent_runtime import Model, step

from jarvis_brain.desktop.worker import Session
from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.agent.capabilities import BuiltinCapabilities
from jarvis_brain.intelligence.agent.runner import AgentRuntime
from jarvis_brain.intelligence.file_session import FileSession


def core_for(topic="budget"):
    core = SyntheticCore()
    core.entries = [
        {"entry_id": f"item-{i}", "name": name, "kind": "file", "location": f"Downloads/{name}"}
        for i, name in enumerate(
            [f"{topic}-archive.pdf", f"{topic}-draft.pdf", f"{topic}-final.pdf"], 1
        )
    ]
    return core


def test_zero_name_match_returns_labeled_same_scope_metadata_preserving_other_filters():
    core = SyntheticCore()
    builtins = BuiltinCapabilities(core)
    result = builtins.find_files(
        {"query": "unknown-subject", "location": "Masaüstü", "recursive": False, "category": "text"}
    )
    assert result.data["original_name_matches"] == 0
    assert result.data["original_name_query"] == "unknown-subject"
    assert result.data["match_basis"] == "same_scope_alternatives_not_name_matches"
    assert len(result.data["interpretation"]) <= 512
    assert result.data["applied_filters"]["query"] == "*"
    assert result.data["results"][0]["name"] == "New Metin Belgesi.txt"
    assert core.calls[-1]["arguments"]["folder_id"] == "desk"
    assert core.calls[-1]["arguments"]["recursive"] is False
    assert core.calls[-1]["arguments"]["category"] == "text"
    assert len(core.calls) == 3  # Verified scope, exact query, labeled bounded alternatives.
    assert not result.terminal


def test_inline_enumerations_require_one_selection_but_normal_comparisons_remain_prose():
    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    recommendations = builtins.recommendations
    recommendations.needs_presentation = False
    feedback = recommendations.answer_feedback(
        "Available: budget-archive.pdf, budget-draft.pdf and budget-final.pdf."
    )
    assert feedback["required_actions"] == ["suggest_result", "show_results"]
    recommendations.needs_presentation = False
    assert (
        recommendations.answer_feedback(
            "budget-archive.pdf differs from budget-draft.pdf in its name."
        )
        is None
    )


def test_required_saved_name_keeps_zero_results_and_never_fetches_alternative_names():
    core = SyntheticCore()
    builtins = BuiltinCapabilities(core)
    result = builtins.find_files(
        {"query": "missing-report.pdf", "location": "Masaüstü", "name_is_constraint": True}
    )
    assert result.data["total"] == 0
    assert result.data["applied_filters"]["name_is_constraint"] is True
    assert "match_basis" not in result.data and not builtins.recommendations.items()
    assert len(core.calls) == 2
    assert core.calls[-1]["arguments"]["query"] == "missing-report.pdf"


def test_required_name_cannot_become_a_wildcard_before_any_core_call():
    core = SyntheticCore()
    result = BuiltinCapabilities(core).find_files(
        {"name_is_constraint": True, "location": "Masaüstü"}
    )
    assert result.data["error"] == "missing_required_name" and not core.calls


@pytest.mark.parametrize("topic", ["budget", "presentation", "recipe", "warranty"])
def test_model_can_prefer_a_non_first_candidate_without_listing_or_opening(topic):
    core = core_for(topic)
    model = Model(step("find_files", query=topic), step("suggest_result", number=3))
    runtime = AgentRuntime(core, model)
    result = runtime.handle(f"Could you find my {topic} final?")
    state = runtime.builtins.recommendations
    assert state.items()[0]["number"] == 3
    assert f"{topic}-final.pdf" in result.message
    assert (
        f"{topic}-archive.pdf" not in result.message and f"{topic}-draft.pdf" not in result.message
    )
    assert len(state.items()) == 1 and not result.executed
    assert [c["tool"] for c in core.calls] == ["search_files"]
    assert "entry_id" not in repr(model.snapshots) and "Downloads/" not in repr(model.snapshots)


def test_rejection_removes_only_proposed_identity_and_refreshes_context_in_same_turn():
    core = core_for()
    model = Model(
        step("find_files", query="budget"),
        step("suggest_result", number=2),
        step("reject_suggestion", number=2),
        step("suggest_result", number=3),
    )
    runtime = AgentRuntime(core, model)
    runtime.handle("Find my budget")
    core.calls.clear()
    result = runtime.handle("No, that isn't the one.")
    assert "budget-final.pdf" in result.message and "budget-draft.pdf" not in result.message
    assert not core.calls
    view = model.snapshots[-1]["capability_context"]
    assert {c["number"] for c in view["files"]["current_results"]} == {1, 3}
    assert "budget-draft.pdf" in view["recommendations"]["rejected_names"]
    assert runtime.builtins.recommendations.suggest({"number": 2}).data["error"]
    assert not runtime.builtins.open_result({"number": 2}).performed


def test_requery_automatically_excludes_rejected_candidate_but_not_unseen_rows():
    core = core_for()
    builtins = BuiltinCapabilities(core)
    builtins.find_files({"query": "budget"})
    builtins.recommendations.suggest({"number": 2})
    builtins.recommendations.reject({"number": 2})
    builtins.find_files({"query": "budget"})
    assert core.calls[-1]["arguments"]["exclude_ids"] == ["item-2"]
    assert {r["name"] for r in builtins.recommendations.remaining()} == {
        "budget-archive.pdf",
        "budget-final.pdf",
    }


def test_legacy_exclude_previous_rejects_only_visible_suggestion():
    core = core_for()
    builtins = BuiltinCapabilities(core)
    builtins.find_files({"query": "budget"})
    builtins.recommendations.suggest({"number": 3})
    builtins.find_files({"query": "budget", "exclude_previous": True})
    assert core.calls[-1]["arguments"]["exclude_ids"] == ["item-3"]


def test_identity_confirmation_never_opens_then_explicit_open_still_checks_permission():
    core = core_for()
    model = Model(
        step("find_files", query="budget"),
        step("suggest_result", number=2),
        step("answer", message="Great, we found it."),
        step("open_result", number=2),
        authorized=True,
    )
    runtime = AgentRuntime(core, model)
    runtime.handle("Help me locate my budget")
    core.calls.clear()
    result = runtime.handle("Yes, that is mine.")
    assert not result.executed and not core.calls and not model.permissions
    result = runtime.handle("Open it, please.")
    assert result.executed and core.calls[-1]["arguments"] == {"entry_id": "item-2"}
    assert model.permissions[-1][0] == "Open it, please."


def test_explicit_full_list_is_available_without_renumbering_survivors():
    core = core_for()
    model = Model(
        step("find_files", query="budget"),
        step("suggest_result", number=2),
        step("reject_suggestion", number=2),
        step("show_results"),
        step("answer", message="Here are the other matches."),
        authorized=True,
    )
    runtime = AgentRuntime(core, model)
    runtime.handle("Find my budget")
    result = runtime.handle("Not that one; show all the other options.")
    assert "1. budget-archive.pdf" in result.message and "3. budget-final.pdf" in result.message
    assert "budget-draft.pdf" not in result.message
    assert [r["number"] for r in runtime.builtins.recommendations.items()] == [1, 3]
    assert "Downloads/" not in repr(runtime.memory.snapshot())


def test_expiry_and_reset_clear_suggestion_authority_without_extending_bindings():
    now = [0]
    core = core_for()
    files = FileSession(core, clock=lambda: now[0])
    builtins = BuiltinCapabilities(core, files)
    builtins.find_files({"query": "budget"})
    builtins.recommendations.suggest({"number": 2})
    now[0] = 121
    assert builtins.recommendations.suggest({"number": 2}).data["error"]
    assert not builtins.recommendations.items()
    builtins.clear_files()
    assert not builtins.recommendations.rejected and builtins.recommendations.selected is None


def test_stale_and_hidden_desktop_cards_never_open_with_a_current_page_token():
    core = core_for()
    session = Session(
        core, Model(step("find_files", query="budget"), step("suggest_result", number=2))
    )
    page = session.request({"op": "chat", "text": "Find my budget"})
    core.calls.clear()
    with pytest.raises(ValueError, match="page has changed"):
        session.request({"op": "select", "number": 1, "page_token": page["page_token"]})
    assert not core.calls


@pytest.mark.parametrize(
    "args", [{"number": True}, {"number": 0}, {"number": 21}, {"number": 1, "entry_id": "injected"}]
)
def test_invalid_proposal_cannot_supply_authority(args):
    import json

    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    with pytest.raises(ModelOutputInvalid):
        builtins.registry().parse(
            json.dumps({"action": "suggest_result", "arguments": args, "confidence": 1})
        )


def test_duplicate_names_are_rejected_by_private_identity_not_name():
    core = core_for()
    for entry in core.entries:
        entry["name"] = "budget.pdf"
    builtins = BuiltinCapabilities(core)
    builtins.find_files({"query": "budget"})
    first = builtins.files._entries[0]["entry_id"]
    builtins.recommendations.suggest({"number": 1})
    builtins.recommendations.reject({"number": 1})
    assert len(builtins.recommendations.remaining()) == 2
    assert builtins.recommendations.excluded_files() == [first]
    assert builtins.recommendations.suggest({"number": 2}).terminal


def test_no_candidates_remain_after_rejecting_each_one_and_suggestion_tool_disappears():
    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    for number in [2, 3, 1]:
        builtins.recommendations.suggest({"number": number})
        builtins.recommendations.reject({"number": number})
    assert not builtins.recommendations.items() and not builtins.recommendations.remaining()
    assert "suggest_result" not in {tool["name"] for tool in builtins.registry().descriptions()}


def test_ambiguous_apps_support_one_suggestion_and_rejection_within_original_ttl():
    from services.brain.tests.integration.test_english_agent_acceptance import AppCore

    core = AppCore(ambiguous=True)
    builtins = BuiltinCapabilities(core)
    registry = builtins.registry()
    registry.begin_turn()
    builtins.open_app({"query": "Studio"})
    builtins.recommendations.suggest({"number": 2})
    expires = builtins.app_choices._expires
    registry.finish_turn()
    core.calls.clear()
    registry.begin_turn()
    builtins.recommendations.reject({"number": 2})
    registry.finish_turn()
    assert builtins.app_choices._expires == expires
    assert builtins.recommendations.suggest({"number": 1}).terminal
    assert builtins.recommendations.items()[0]["name"] == "Studio Alpha"
    assert not core.calls


def test_presentation_gate_repairs_a_prose_list_without_leaking_the_draft():
    core = core_for()
    model = Model(
        step("find_files", query="budget"),
        step(
            "answer",
            message="Here are all three: budget-archive.pdf, budget-draft.pdf, budget-final.pdf",
        ),
        step("suggest_result", number=3),
    )
    runtime = AgentRuntime(core, model)
    response = runtime.handle("Find my budget")
    assert "budget-final.pdf" in response.message and "budget-archive.pdf" not in response.message
    assert model.snapshots[-1]["response_feedback"]["error"] == "presentation_selection_required"


def test_suggestion_replacement_requires_explicit_rejection_before_switching():
    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    builtins.recommendations.suggest({"number": 3})
    response = builtins.recommendations.suggest({"number": 2})
    assert response.data["error"] == "suggestion_transition_required"
    assert builtins.recommendations.proposed()["number"] == 3


def test_failed_in_memory_transition_can_retry_after_rejection_without_replaying_core():
    core = core_for()
    model = Model(
        step("find_files", query="budget"),
        step("suggest_result", number=3),
        step("suggest_result", number=2),
        step("reject_suggestion", number=3),
        step("suggest_result", number=2),
    )
    runtime = AgentRuntime(core, model)
    runtime.handle("Find budget")
    core.calls.clear()
    response = runtime.handle("No, try another")
    assert "budget-draft.pdf" in response.message
    assert runtime.builtins.recommendations.view()["rejected_names"] == ["budget-final.pdf"]
    assert not core.calls


def test_provider_repair_schema_contains_only_registered_presentation_actions(monkeypatch):
    from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    registry = builtins.registry()
    captured = []
    model = QwenGgufIntentModel()

    def generate(system, payload, schema, context):
        captured.append(schema)
        return step("suggest_result", number=3)

    monkeypatch.setattr(model, "_agent_generate", generate)
    value = model.next_step(
        {
            "current_request": "Find budget",
            "response_feedback": builtins.recommendations.answer_feedback(),
        },
        registry.descriptions(),
        registry.schema(),
    )
    assert registry.parse(value).arguments == {"number": 3}
    assert {c["properties"]["action"]["const"] for c in captured[0]["oneOf"]} == {
        "suggest_result",
        "show_results",
    }


def test_retry_permission_is_rejected_for_core_backed_or_side_effecting_capabilities():
    from jarvis_brain.intelligence.agent.capabilities import execute_capability
    from jarvis_brain.intelligence.agent.registry import Capability, Observation, object_schema

    for effect, requires in [("act", ()), ("observe", ("search_files",))]:
        capability = Capability(
            "example",
            "Test retry boundary",
            object_schema(),
            lambda args: Observation({"error": "test"}, retryable=True),
            effect,
            "test",
            requires,
        )
        with pytest.raises(ModelOutputInvalid):
            execute_capability(capability, {})


def test_presentation_repair_is_consumed_before_following_prose_reply():
    from jarvis_brain.intelligence.agent.registry import (
        Capability,
        CapabilityRegistry,
        Observation,
        object_schema,
    )

    state = {"pending": True}

    def choose(args):
        state["pending"] = False
        return Observation({"selected": True})

    registry = CapabilityRegistry(
        [Capability("choose_label", "Select a display label", object_schema(), choose)]
    )
    registry.register_response_check(
        "label",
        lambda message: (
            {"error": "label_required", "required_actions": ["choose_label"]}
            if state["pending"]
            else None
        ),
    )
    model = Model(
        step("answer", message="Draft"), step("choose_label"), step("answer", message="Ready")
    )
    runtime = AgentRuntime(core_for(), model, registry=registry)
    assert runtime.handle("Choose a label").message == "Ready"
    assert "response_feedback" in model.snapshots[-2]
    assert "response_feedback" not in model.snapshots[-1]


def test_provider_does_not_repair_invalid_tool_proposals_or_overlong_prose(monkeypatch):
    from jarvis_brain.intelligence.models.qwen_gguf import QwenGgufIntentModel

    registry = BuiltinCapabilities(core_for()).registry()
    model = QwenGgufIntentModel()
    monkeypatch.setattr(model, "_format_agent_messages", lambda *args, **kwargs: "prompt")

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid native output must fail closed, never turn into an action")

    monkeypatch.setattr(model, "_agent_generate", forbidden)
    for output in [
        "long prose " * 120,
        "x" * 2100,
        "<tool_call>malformed</tool_call>",
        '<tool_call>{"name":"answer","arguments":{"message":17}}</tool_call>',
    ]:
        monkeypatch.setattr(model, "_generate", lambda *args, output=output, **kwargs: output)
        with pytest.raises(ModelOutputInvalid):
            registry.parse(
                model.next_step(
                    {"current_request": "Hi"}, registry.descriptions(), registry.schema()
                )
            )


def test_followup_prose_enumeration_requires_matching_visible_list_selection():
    model = Model(
        step("find_files", query="budget"),
        step("suggest_result", number=3),
        step("answer", message="1. budget-archive.pdf\n2. budget-draft.pdf\n3. budget-final.pdf"),
        step("show_results"),
        step("answer", message="The remaining options."),
        authorized=True,
    )
    runtime = AgentRuntime(core_for(), model)
    runtime.handle("Find budget")
    response = runtime.handle("Show all the options")
    assert runtime.builtins.recommendations.mode == "all"
    assert len(runtime.builtins.recommendations.items()) == 3
    assert "budget-archive.pdf" in response.message


def test_prose_comparison_does_not_become_a_list_or_lose_the_suggestion():
    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    builtins.recommendations.suggest({"number": 3})
    builtins.recommendations.begin_turn()
    assert (
        builtins.recommendations.answer_feedback(
            "budget-archive.pdf and budget-final.pdf have different version labels in their names."
        )
        is None
    )
    assert builtins.recommendations.mode == "single"


def test_full_list_speech_uses_original_numbers_and_never_reads_private_locations():
    core = core_for()
    builtins = BuiltinCapabilities(core)
    builtins.find_files({"query": "budget"})
    builtins.recommendations.suggest({"number": 2})
    builtins.recommendations.reject({"number": 2})
    result = builtins.show_results({})
    assert result.terminal and result.memory_message == "1. budget-archive.pdf\n3. budget-final.pdf"
    assert "Downloads/" in result.display and "Downloads/" not in result.memory_message


def test_tentative_suggestion_does_not_lower_confidence_for_machine_actions():
    import json

    core = core_for()
    tentative = json.dumps(
        {"action": "suggest_result", "arguments": {"number": 3}, "confidence": 0.3}
    )
    uncertain_open = json.dumps(
        {"action": "open_result", "arguments": {"number": 3}, "confidence": 0.3}
    )
    runtime = AgentRuntime(
        core, Model(step("find_files", query="budget"), tentative, uncertain_open)
    )
    assert "budget-final.pdf" in runtime.handle("Find budget").message
    core.calls.clear()
    assert not runtime.handle("Open it").executed and not core.calls


def test_machine_capabilities_cannot_override_the_global_confidence_threshold():
    from jarvis_brain.intelligence.agent.registry import (
        Capability,
        CapabilityRegistry,
        Observation,
        object_schema,
    )

    for effect, requires in [("act", ()), ("observe", ("search_files",))]:
        with pytest.raises(ValueError):
            CapabilityRegistry(
                [
                    Capability(
                        "example",
                        "A capability",
                        object_schema(),
                        lambda args: Observation({}),
                        effect,
                        "permission",
                        requires,
                        minimum_confidence=0.0,
                    )
                ]
            )


def test_full_list_keeps_all_private_rows_while_model_names_remain_bounded():
    core = core_for()
    core.entries = [
        {
            "entry_id": f"long-{i}",
            "name": f"budget-{i:02}-" + "x" * 100 + ".txt",
            "kind": "file",
            "location": f"Downloads/long-{i}.txt",
        }
        for i in range(20)
    ]
    model = Model(step("find_files", query="budget"), step("show_results"), authorized=True)
    session = Session(core, model)
    result = session.request({"op": "chat", "text": "Show all budget files"})
    assert len(result["items"]) == 20
    assert len(model.snapshots[-1]["capability_context"]["files"]["current_results"]) < 20
    core.calls.clear()
    opened = session.request({"op": "select", "number": 20, "page_token": result["page_token"]})
    assert opened["executed"] and core.calls[-1]["arguments"] == {"entry_id": "long-19"}


def test_cli_keeps_partial_scope_notice_separate_from_spoken_suggestion():
    builtins = BuiltinCapabilities(core_for())
    builtins.find_files({"query": "budget"})
    builtins.files._page_info["partial"] = True
    suggestion = builtins.recommendations.suggest({"number": 3})
    assert "Partial catalog" in suggestion.display
    assert suggestion.memory_message == "Could budget-final.pdf be the one you're looking for?"
    listed = builtins.show_results({})
    assert "Partial catalog" in listed.display and "Partial catalog" not in listed.memory_message


def test_exhausted_suggestion_page_is_not_reported_as_a_new_catalog_search():
    core = core_for()
    builtins = BuiltinCapabilities(core)
    builtins.find_files({"query": "budget"})
    core.calls.clear()
    for number in [1, 2, 3]:
        builtins.recommendations.suggest({"number": number})
        rejected = builtins.recommendations.reject({"number": number})
    assert rejected.data["page_exhausted"] and rejected.data["search_performed"] is False
    assert "OLD result page" in rejected.data["recovery"] and not core.calls
