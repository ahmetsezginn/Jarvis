"""Semantic desktop shutdown; only a verified native result can terminate the frontend."""

from jarvis_brain.errors import CoreToolError
from jarvis_brain.intelligence.agent.presentation import operation_failure
from jarvis_brain.intelligence.agent.registry import Capability, Observation, object_schema


class DesktopCapabilities:
    def __init__(self, core):
        self.core = core
        self.event = None

    def clear(self):
        self.event = None

    def register(self, registry):
        registry.register(
            Capability(
                "close_assistant_window",
                "Close JARVIS's desktop application and stop its conversation worker. Use when "
                "the user dismisses you or gives permission to close yourself. This permission "
                "is an instruction, not a capability question; no extra confirmation needed. "
                "Ends this in-memory conversation and releases the language model. Does not "
                "shut down Windows. Saved personal tasks and notes remain stored. No background "
                "wake listener is installed; open JARVIS manually to start a new session.",
                object_schema(),
                self.close,
                "act",
                "Close JARVIS's desktop application and stop its conversation worker",
                requires=("desktop_close",),
                review_on_answer=True,
            )
        )
        registry.register_context("desktop", lambda: {}, self.clear, begin=self.clear)

    def close(self, args):
        try:
            data = self.core.execute_tool("desktop_close", {}).data
        except CoreToolError as error:
            return Observation({"error": error.code}, operation_failure(error.code), terminal=True)
        self.event = {"closing": data["closing"], "revision": data["revision"]}
        return Observation(
            {"desktop_closing": data["closing"]}, "Closing JARVIS.", performed=True, terminal=True
        )
