"""Bounded observe/decide/act loop, independent of individual capabilities and providers."""

from __future__ import annotations

import copy
import json
import math
import re
import threading
import time
from dataclasses import asdict

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.agent.capabilities import BuiltinCapabilities, execute_capability
from jarvis_brain.intelligence.contract import BrainResponse, IntentName
from jarvis_brain.intelligence.conversation import ConversationMemory
from jarvis_brain.intelligence.models.base import EffectAssessment


class AgentRuntime:
    def __init__(
        self,
        core,
        model,
        *,
        files=None,
        registry=None,
        minimum_confidence=0.8,
        context=None,
        clock=time.monotonic,
        max_steps=5,
    ):
        if not 1 <= max_steps <= 8:
            raise ValueError("agent step limit must be between 1 and 8")
        self.model = model
        self.builtins = BuiltinCapabilities(core, files)
        self.files = self.builtins.files
        self.registry = registry or self.builtins.registry()
        if callable(getattr(core, "list_tools", None)):
            self.registry = self.registry.supported_by(tool.name for tool in core.list_tools())
        self.minimum_confidence = minimum_confidence
        self.context = context
        self.clock = clock
        self.max_steps = max_steps
        self.memory = ConversationMemory()
        self._lock = threading.RLock()
        self.trace = []
        self.reset()

    def reset(self):
        with self._lock:
            self.memory.clear()
            self.files.clear()
            self.registry.clear_contexts()
            self.observations = []
            self.expires = 0
            self.trace = []
            self.pending = None
            self._tool_turns = {}
            self._this_turn_events = []

    def _response(
        self, text, message, *, performed=False, intent=IntentName.RESPOND, memory_message=None
    ):
        response = BrainResponse(intent, 1, "agent", performed, message)
        # User-visible paths are deliberately outside model memory.
        remembered = BrainResponse(
            intent, 1, "agent", performed, message if memory_message is None else memory_message
        )
        self.memory.observe(text, remembered)
        turns = self.memory.snapshot()
        if turns and self._this_turn_events:
            self._tool_turns[id(turns[-1])] = (
                self.clock() + 120,
                copy.deepcopy(self._this_turn_events[-3:]),
                turns[-1],
            )
        alive = {id(turn) for turn in turns}
        self._tool_turns = {
            key: value
            for key, value in self._tool_turns.items()
            if key in alive and self.clock() < value[0]
        }
        # Three verified observations overall, attached to their actual originating turn.
        budget = 3
        for turn in reversed(turns):
            key = id(turn)
            if key in self._tool_turns:
                expiry, events, owner = self._tool_turns[key]
                retained = events[-budget:] if budget else []
                self._tool_turns[key] = (expiry, retained, owner)
                budget -= len(retained)
        return response

    def snapshot(self, text):
        if self.clock() >= self.expires:
            self.observations.clear()
        history = []
        for turn in self.memory.snapshot():
            item = asdict(turn)
            expiry, events, owner = self._tool_turns.get(id(turn), (0, [], None))
            if owner is turn and self.clock() < expiry and events:
                item["tool_events"] = copy.deepcopy(events)
            history.append(item)
        # Model memory contains the reply only; user-visible result paths are kept outside it.
        views = {
            name: safe_observation(view) for name, view in self.registry.context_views().items()
        }
        return {
            "recent_conversation": history,
            "recent_tools": copy.deepcopy(self.observations[-3:]),
            "capability_context": views,
            "current_request": text,
        }

    def handle(self, text):
        with self._lock:
            self.registry.begin_turn()
            try:
                return self._handle(text)
            finally:
                self.registry.finish_turn()

    def _handle(self, text):
        self._this_turn_events = []
        if text.casefold() in {"/reset", "iptal", "vazgeç", "vazgec", "cancel", "boşver", "bosver"}:
            self.reset()
            return self._response(text, "Pending task and session context cleared.")
        self.trace = []
        pending, self.pending = self.pending, None
        if pending and self.clock() < pending[1]:
            if text.casefold() in {"evet", "aynen", "tamam", "yes"}:
                result = pending[0]()
                return self._response(
                    text,
                    result.display or "This selection has expired.",
                    performed=result.performed,
                )
            if text.casefold() in {"hayır", "hayir", "no"}:
                return self._response(text, "Pending opening cancelled.")
        reference = self.registry.reference(text)
        if reference is not None and not reference.valid:
            return self._response(text, "No current result has that number; find the item first.")
        # A bare row number is the UI's explicit selection syntax, not natural-language inference.
        if re.fullmatch(r"[0-9]{1,2}[.)]?", text) and reference is not None:
            result = execute_capability(
                self.registry.get(reference.shorthand), {"number": reference.number}
            )
            return self._response(text, result.display, performed=result.performed)
        self.model.load()
        initial = self.snapshot(text)
        turn_events = []
        seen = set()
        display = ""
        performed = False
        for _ in range(self.max_steps):
            snapshot = {**initial, "turn_events": turn_events}
            raw = self.model.next_step(
                copy.deepcopy(snapshot),
                self.registry.descriptions(),
                self.registry.schema(),
                self.context,
            )
            step = self.registry.parse(raw)
            self.trace.append({"step": step.action, "arguments": step.arguments})
            if step.action == "answer":
                message = step.arguments["message"]
                return self._response(
                    text,
                    message + ("\n" + display if display else ""),
                    performed=performed,
                    memory_message=message,
                )
            if step.confidence < self.minimum_confidence:
                return self._response(
                    text,
                    "I could not understand the request confidently. Could you clarify?",
                    performed=performed,
                )
            if reference is not None and (
                step.action not in reference.actions
                or step.arguments.get("number") != reference.number
            ):
                return self._response(
                    text, "That number refers to the current list; no new search was performed."
                )
            signature = json.dumps(
                [step.action, step.arguments], sort_keys=True, ensure_ascii=False
            )
            if signature in seen:
                return self._response(
                    text,
                    "I need another clue to proceed without repeating the same step."
                    + ("\n" + display if display else ""),
                    performed=performed,
                    memory_message="The repeated tool step was stopped; another clue is needed.",
                )
            seen.add(signature)
            capability = self.registry.get(step.action)
            if capability.effect != "observe":
                proposal = {"operation": capability.permission, "parameters": step.arguments}
                if capability.authorization_view is not None:
                    proposal["target"] = safe_observation(
                        capability.authorization_view(step.arguments)
                    )
                assessment = self.model.authorize_action(text, proposal, self.context)
                wanted = ""
                if isinstance(assessment, EffectAssessment):
                    authorized = assessment.authorized
                    wanted = assessment.requested_outcome
                    if not isinstance(wanted, str) or not 1 <= len(wanted) <= 160:
                        raise ModelOutputInvalid("invalid requested-outcome assessment")
                    safe_observation({"requested_outcome": wanted})
                else:
                    authorized = assessment
                if type(authorized) is not bool:
                    raise ModelOutputInvalid("invalid current-request authorization")
                if not authorized:
                    turn_events.append(
                        {
                            "action": step.action,
                            "arguments": step.arguments,
                            "result": {
                                "error": "not_authorized_current_request",
                                **({"requested_outcome": wanted} if wanted else {}),
                                "reason": (
                                    "The proposal does not match the current request. "
                                    "Correct parameters only for the SAME requested operation. "
                                    "Do not work around an unrequested/different operation "
                                    "with preparatory actions."
                                ),
                            },
                        }
                    )
                    continue
            observation = execute_capability(capability, step.arguments)
            safe = safe_observation(observation.data)
            turn_events.append({"action": step.action, "arguments": step.arguments, "result": safe})
            self._this_turn_events.append(
                {
                    "action": step.action,
                    "arguments": step.arguments,
                    "result": {key: value for key, value in safe.items() if key != "results"},
                }
            )
            self.trace.append({"observation": safe})
            self.observations.append(
                {
                    "action": step.action,
                    "arguments": step.arguments,
                    "result": {key: value for key, value in safe.items() if key != "results"},
                }
            )
            self.observations = self.observations[-3:]
            self.expires = self.clock() + 120
            if observation.display:
                display = observation.display
            performed |= observation.performed
            if observation.terminal:
                if observation.confirmation is not None:
                    self.pending = (observation.confirmation, self.clock() + 120)
                return self._response(
                    text,
                    display or "The operation was not completed.",
                    performed=observation.performed,
                )
        return self._response(
            text,
            "I reached the step limit for this turn; please review the current results."
            + ("\n" + display if display else ""),
            performed=performed,
            memory_message="The step limit for this turn was reached.",
        )


def safe_observation(data):
    """Capabilities return explicit model views, never raw Core envelopes or private bindings."""
    if not isinstance(data, dict):
        raise ModelOutputInvalid("observation must be a structured object")

    def check(value, depth=0):
        if depth > 6:
            raise ModelOutputInvalid("observation nesting limit exceeded")
        if isinstance(value, dict):
            if any(
                key in {"entry_id", "app_id", "folder_id", "path", "location", "request_id"}
                for key in value
            ):
                raise ModelOutputInvalid("private authority in model observation")
            return {key: check(item, depth + 1) for key, item in value.items()}
        if isinstance(value, list):
            if len(value) > 20:
                raise ModelOutputInvalid("observation list limit exceeded")
            return [check(item, depth + 1) for item in value]
        if isinstance(value, str):
            if len(value) > 512 or re.search(
                r"(?<![A-Za-z0-9])[a-zA-Z]:[\\/]|\\\\|<\|(?:im_start|im_end)\|>", value
            ):
                raise ModelOutputInvalid("unsafe observation text")
            return value
        if type(value) is float and not math.isfinite(value):
            raise ModelOutputInvalid("non-finite observation number")
        if value is None or type(value) in (bool, int, float):
            return value
        raise ModelOutputInvalid("invalid observation value")

    result = check(data)
    # Current results have their own separately bounded page view; don't duplicate it in history.
    if len(json.dumps(result, ensure_ascii=False)) > 3200:
        raise ModelOutputInvalid("observation size limit exceeded")
    return result
