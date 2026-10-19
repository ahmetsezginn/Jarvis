import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.agent.desktop import DesktopCapabilities
from jarvis_brain.intelligence.agent.registry import CapabilityRegistry, object_schema, text_schema
from jarvis_brain.intelligence.agent.runner import AgentRuntime, safe_observation


class Core:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def execute_tool(self, tool, args):
        self.calls.append((tool, args))
        if self.error:
            raise self.error
        return SimpleNamespace(data={"closing": True, "revision": 3})


def test_only_core_acknowledgement_yields_a_window_event_and_it_expires_each_turn():
    core = Core()
    bundle = DesktopCapabilities(core)
    registry = CapabilityRegistry()
    bundle.register(registry)
    result = bundle.close({})
    assert result.performed and result.terminal
    assert bundle.event == {"closing": True, "revision": 3}
    assert "session" not in safe_observation(result.data)
    assert core.calls == [("desktop_close", {})]
    registry.begin_turn()
    assert bundle.event is None


def test_missing_core_support_filters_out_lifecycle_capability():
    registry = CapabilityRegistry()
    DesktopCapabilities(Core()).register(registry)
    assert not registry.supported_by([]).descriptions()


@pytest.mark.parametrize("code", ["policy_denied", "execution_failed", "unknown_tool"])
def test_rejection_never_creates_a_window_event(code):
    bundle = DesktopCapabilities(Core(CoreToolError(code, "test")))
    result = bundle.close({})
    assert not result.performed and result.terminal
    assert bundle.event is None


class ReviewModel:
    def __init__(self, requested=True, authorized=True):
        self.requested, self.authorized = requested, authorized
        self.reviews, self.permissions = [], []
        self.turn = 0

    def load(self):
        pass

    def next_step(self, snapshot, *_):
        self.turn += 1
        if snapshot.get("response_feedback", {}).get("unperformed_requested_action"):
            return json.dumps(
                {"action": "close_assistant_window", "arguments": {}, "confidence": 1}
            )
        return json.dumps(
            {"action": "answer", "arguments": {"message": "Understood."}, "confidence": 1}
        )

    def assess_omitted_action(self, text, effect, context):
        self.reviews.append((text, effect))
        return self.requested

    def authorize_action(self, text, effect, context):
        self.permissions.append((text, effect))
        return self.authorized


def test_omission_review_replans_but_does_not_authorize_execution():
    for requested, authorized, count in [(True, True, 1), (True, False, 0), (False, True, 0)]:
        core, model = Core(), ReviewModel(requested, authorized)
        registry = CapabilityRegistry()
        DesktopCapabilities(core).register(registry)
        runtime = AgentRuntime(core, model, registry=registry)
        response = runtime.handle("A semantic request, interpreted by the provider.")
        assert len(core.calls) == count
        assert response.executed is bool(count)
        assert len(model.reviews) == 1
        assert len(model.permissions) == int(requested)


def test_omission_review_is_restricted_to_parameterless_effects():
    registry = CapabilityRegistry()
    DesktopCapabilities(Core()).register(registry)
    capability = registry.get("close_assistant_window")
    for changed in [
        replace(capability, effect="observe"),
        replace(capability, parameters=object_schema(target=text_schema())),
        replace(capability, review_on_answer="yes"),
        replace(capability, authorization_view=lambda args: {}),
    ]:
        with pytest.raises(ValueError):
            CapabilityRegistry([changed])


def test_malformed_omission_assessment_cannot_request_an_action():
    from jarvis_brain.errors import ModelOutputInvalid

    core, model = Core(), ReviewModel()
    model.assess_omitted_action = lambda *_: "false"
    registry = CapabilityRegistry()
    DesktopCapabilities(core).register(registry)
    with pytest.raises(ModelOutputInvalid):
        AgentRuntime(core, model, registry=registry).handle("Untrusted provider output")
    assert not core.calls
