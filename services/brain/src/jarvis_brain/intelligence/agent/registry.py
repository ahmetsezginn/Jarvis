"""Closed per-run tool surface; schemas and dispatch share one registry."""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Callable
from dataclasses import dataclass

from jarvis_brain.errors import ModelOutputInvalid
from jarvis_brain.intelligence.contract import validate_intent_object
from jarvis_brain.intelligence.parser import parse_json_object


@dataclass(frozen=True)
class Observation:
    """Model-safe feedback and separately rendered, user-visible output."""

    data: dict
    display: str = ""
    performed: bool = False
    terminal: bool = False
    confirmation: Callable[[], Observation] | None = None
    retryable: bool = False
    memory_message: str | None = None
    conversation_display: bool = False


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], Observation]
    effect: str = "observe"
    permission: str = ""
    requires: tuple[str, ...] = ()
    authorization_view: Callable[[dict], dict] | None = None
    available: Callable[[], bool] | None = None
    minimum_confidence: float | None = None
    review_on_answer: bool = False


@dataclass(frozen=True)
class AgentStep:
    action: str
    arguments: dict
    confidence: float


@dataclass(frozen=True)
class ResultReference:
    """Capability-owned UI binding; constrains identity without granting an action."""

    number: int
    actions: tuple[str, ...]
    shorthand: str
    valid: bool


class CapabilityRegistry:
    def __init__(self, capabilities=()):
        self._tools: dict[str, Capability] = {}
        self._contexts = {}
        self._references = {}
        self._response_checks = {}
        self._reference_focus = {"owner": None}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: Capability):
        if (
            not isinstance(capability, Capability)
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", capability.name)
            or capability.name == "answer"
            or capability.name in self._tools
            or capability.effect not in {"observe", "act"}
            or (capability.effect != "observe" and not capability.permission)
            or not callable(capability.handler)
            or not isinstance(capability.description, str)
            or not 1 <= len(capability.description) <= 800
            or not isinstance(capability.requires, tuple)
            or any(not isinstance(name, str) for name in capability.requires)
            or (
                capability.authorization_view is not None
                and not callable(capability.authorization_view)
            )
            or (capability.available is not None and not callable(capability.available))
            or type(capability.review_on_answer) is not bool
            or (
                capability.review_on_answer
                and (
                    capability.effect != "act"
                    or not isinstance(capability.parameters, dict)
                    or capability.parameters.get("properties")
                    or capability.authorization_view is not None
                )
            )
            or (
                capability.minimum_confidence is not None
                and (
                    capability.effect != "observe"
                    or capability.requires
                    or type(capability.minimum_confidence) not in (int, float)
                    or not math.isfinite(capability.minimum_confidence)
                    or not 0 <= capability.minimum_confidence <= 1
                )
            )
        ):
            raise ValueError("invalid or duplicate capability registration")
        # Validate the supported schema vocabulary at registration, not after inference.
        _check_schema(capability.parameters)
        self._tools[capability.name] = Capability(
            capability.name,
            capability.description,
            copy.deepcopy(capability.parameters),
            capability.handler,
            capability.effect,
            capability.permission,
            capability.requires,
            capability.authorization_view,
            capability.available,
            capability.minimum_confidence,
            capability.review_on_answer,
        )

    def supported_by(self, core_tools):
        available = set(core_tools)
        registry = CapabilityRegistry(
            tool for tool in self._tools.values() if set(tool.requires) <= available
        )
        registry._contexts = dict(self._contexts)
        registry._references = dict(self._references)
        registry._response_checks = dict(self._response_checks)
        registry._reference_focus = self._reference_focus
        return registry

    def register_response_check(self, name, check):
        """Trusted capabilities may require structured presentation before a prose answer."""
        if name in self._response_checks or not callable(check):
            raise ValueError("invalid response check")
        self._response_checks[name] = check

    def response_feedback(self, message=""):
        for check in self._response_checks.values():
            feedback = check(message)
            if feedback is not None:
                return feedback
        return None

    def register_reference(self, name, resolve):
        if name in self._references or not callable(resolve):
            raise ValueError("invalid result-reference registration")
        self._references[name] = resolve

    def reference(self, text):
        owner = self._reference_focus["owner"]
        matches = [
            value
            for name, resolve in self._references.items()
            if (owner is None or name == owner) and (value := resolve(text)) is not None
        ]
        if len(matches) > 1 or any(not isinstance(v, ResultReference) for v in matches):
            raise ModelOutputInvalid("ambiguous or invalid result-reference binding")
        return matches[0] if matches else None

    def activate_reference(self, name):
        """Only a trusted bundle displaying a new page may take numbered-selection focus."""
        if name not in self._references:
            raise ValueError("unknown reference owner")
        self._reference_focus["owner"] = name

    def reference_active(self, name):
        return self._reference_focus["owner"] in (None, name)

    def register_context(self, name, view, clear, *, begin=None, finish=None):
        """Trusted bundles expose bounded state and reset hooks without changing the loop."""
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", name)
            or name in self._contexts
            or not callable(view)
            or not callable(clear)
            or (begin is not None and not callable(begin))
            or (finish is not None and not callable(finish))
        ):
            raise ValueError("invalid capability context registration")
        self._contexts[name] = (view, clear, begin, finish)

    def context_views(self):
        result = {}
        for name, (view, _, _, _) in self._contexts.items():
            value = view()
            if value:
                result[name] = copy.deepcopy(value)
        return result

    def clear_contexts(self):
        self._reference_focus["owner"] = None
        for _, clear, _, _ in self._contexts.values():
            clear()

    def begin_turn(self):
        for _, _, begin, _ in self._contexts.values():
            if begin is not None:
                begin()

    def finish_turn(self):
        for _, _, _, finish in self._contexts.values():
            if finish is not None:
                finish()

    def get(self, name):
        try:
            tool = self._tools[name]
        except (KeyError, TypeError) as error:
            raise ModelOutputInvalid("unknown agent capability") from error
        if tool.available is not None and not tool.available():
            raise ModelOutputInvalid("agent capability is not available in current state")
        return tool

    def _available(self):
        return [c for c in self._tools.values() if c.available is None or c.available()]

    def descriptions(self):
        return [
            {
                "name": c.name,
                "description": c.description,
                "parameters": copy.deepcopy(c.parameters),
            }
            for c in self._available()
        ]

    def answer_reviews(self):
        """Opt-in targetless effects whose omission can be reviewed without guessing parameters."""
        return [capability for capability in self._available() if capability.review_on_answer]

    def schema(self):
        actions = [("answer", object_schema(message=text_schema(1024, format="text", minLength=1)))]
        actions.extend((c.name, c.parameters) for c in self._available())
        return {
            "type": "object",
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "action": {"const": name},
                        "arguments": copy.deepcopy(parameters),
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["action", "arguments", "confidence"],
                    "additionalProperties": False,
                }
                for name, parameters in actions
            ],
        }

    def parse(self, raw):
        value = parse_json_object(raw)
        if set(value) != {"action", "arguments", "confidence"}:
            raise ModelOutputInvalid("invalid agent step fields")
        score = value["confidence"]
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ModelOutputInvalid("invalid agent confidence")
        action = value["action"]
        if not isinstance(action, str):
            raise ModelOutputInvalid("invalid agent action")
        schema = (
            object_schema(message=text_schema(1024, format="text", minLength=1))
            if action == "answer"
            else self.get(action).parameters
        )
        _validate(value["arguments"], schema)
        arguments = copy.deepcopy(value["arguments"])
        for name, field in schema["properties"].items():
            if name not in arguments and "default" in field:
                arguments[name] = copy.deepcopy(field["default"])
        return AgentStep(action, arguments, score)


def text_schema(limit=160, **extra):
    return {"type": "string", "maxLength": limit, **extra}


def object_schema(*, optional=(), **properties):
    return {
        "type": "object",
        "properties": properties,
        "required": [name for name in properties if name not in optional],
        "additionalProperties": False,
    }


def _check_schema(schema):
    if not isinstance(schema, dict):
        raise ValueError("capability schema must be an object")
    if schema.get("type") == "object":
        if (
            set(schema) != {"type", "properties", "required", "additionalProperties"}
            or schema["additionalProperties"] is not False
            or not isinstance(schema["properties"], dict)
            or not isinstance(schema["required"], list)
            or any(not isinstance(k, str) for k in schema["required"])
            or len(set(schema["required"])) != len(schema["required"])
            or not set(schema["required"]) <= set(schema["properties"])
            or any(not re.fullmatch(r"[a-z][a-z0-9_]{0,47}", k) for k in schema["properties"])
        ):
            raise ValueError("capabilities require exact object schemas")
        for field in schema["properties"].values():
            _check_schema(field)
    elif schema.get("type") not in {"string", "integer", "boolean"}:
        raise ValueError("unsupported capability schema type")
    elif set(schema) - {
        "type",
        "enum",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "pattern",
        "format",
        "description",
        "default",
    }:
        raise ValueError("unsupported capability schema constraint")
    else:
        kind = schema["type"]
        if (
            any(key in schema for key in ("minLength", "maxLength", "pattern", "format"))
            and kind != "string"
        ):
            raise ValueError("text constraints require strings")
        if any(key in schema for key in ("minimum", "maximum")) and kind != "integer":
            raise ValueError("numeric constraints require integers")
        if "maxLength" in schema and (
            type(schema["maxLength"]) is not int or not 1 <= schema["maxLength"] <= 1024
        ):
            raise ValueError("invalid text bound")
        if "minLength" in schema and (
            type(schema["minLength"]) is not int
            or not 0 <= schema["minLength"] <= schema.get("maxLength", 160)
        ):
            raise ValueError("invalid minimum text bound")
        if "format" in schema and schema["format"] not in {"human_name", "text"}:
            raise ValueError("unsupported capability string format")
        if "description" in schema and (
            not isinstance(schema["description"], str) or not 1 <= len(schema["description"]) <= 400
        ):
            raise ValueError("invalid parameter description")
        for bound in ("minimum", "maximum"):
            if bound in schema and type(schema[bound]) is not int:
                raise ValueError("invalid integer bound")
        if schema.get("minimum", 0) > schema.get("maximum", 20):
            raise ValueError("reversed integer bounds")
        if "pattern" in schema:
            try:
                re.compile(schema["pattern"])
            except (TypeError, re.error) as error:
                raise ValueError("invalid capability pattern") from error
        if "enum" in schema:
            allowed = {"string": str, "integer": int, "boolean": bool}[kind]
            if (
                not isinstance(schema["enum"], list)
                or not schema["enum"]
                or any(type(v) is not allowed for v in schema["enum"])
            ):
                raise ValueError("invalid typed capability enum")
        if "default" in schema:
            try:
                _validate(schema["default"], schema)
            except ModelOutputInvalid as error:
                raise ValueError("invalid typed capability default") from error


def _validate(value, schema, *, field=""):
    kind = schema["type"]
    if kind == "object":
        props = schema["properties"]
        if (
            not isinstance(value, dict)
            or not set(schema["required"]) <= set(value)
            or set(value) - set(props)
        ):
            raise ModelOutputInvalid("invalid capability arguments")
        for key, item in value.items():
            _validate(item, props[key], field=key)
    elif kind == "string":
        if not isinstance(value, str) or not schema.get("minLength", 0) <= len(value) <= schema.get(
            "maxLength", 160
        ):
            raise ModelOutputInvalid("invalid capability text")
        if value:
            if schema.get("format") == "text":
                if any(ord(c) < 32 and c not in "\n\t" for c in value) or any(
                    token in value for token in ("<|", "<think>", "<tool_call>")
                ):
                    raise ModelOutputInvalid("unsafe agent reply")
            else:
                validate_intent_object(
                    {"intent": "open_file", "confidence": 1, "arguments": {"query": value}},
                    model_output=True,
                )
    elif kind == "integer":
        if type(value) is not int or not schema.get("minimum", 0) <= value <= schema.get(
            "maximum", 20
        ):
            raise ModelOutputInvalid("invalid capability number")
    elif kind == "boolean" and type(value) is not bool:
        raise ModelOutputInvalid("invalid capability boolean")
    if "enum" in schema and value not in schema["enum"]:
        raise ModelOutputInvalid("invalid capability choice")
    if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
        raise ModelOutputInvalid("invalid capability text format")
