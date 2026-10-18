"""Opt-in actual Windows device checks. No transcript dispatch or recording persistence."""

import os
import time

import pytest
from jarvis_brain.core.client import JarvisCoreClient

pytestmark = pytest.mark.skipif(
    os.environ.get("JARVIS_RUN_VOICE_DEVICE_LIVE") != "1",
    reason="explicit real microphone and local speaker checks",
)


@pytest.fixture
def core():
    with JarvisCoreClient(request_timeout=120) as client:
        yield client


def test_sustained_push_to_talk_can_release_without_fatal_xrun(core):
    token = core.execute_tool("speech_start", {}).data["recording_id"]
    xruns = 0
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            status = core.execute_tool("speech_poll", {"recording_id": token}).data
            assert status["phase"] == "listening", status
            xruns = max(xruns, status["xruns"])
            time.sleep(0.2)
        arguments = {"recording_id": token, "language": "en"}
        token = None  # finish consumes the token even if recognition fails
        result = core.execute_tool("speech_finish", arguments).data
        assert result["duration_ms"] >= 10000
        assert isinstance(result["text"], str)
        # Never print microphone contents or send them to the agent.
        print(
            "PTT duration_ms:",
            result["duration_ms"],
            "transcript_chars:",
            len(result["text"]),
            "xruns:",
            xruns,
        )
    finally:
        if token:
            core.execute_tool("speech_cancel", {"recording_id": token})


def test_automatic_capture_reports_real_phases_and_cancels_without_transcription(core):
    token = core.execute_tool("speech_start", {"automatic": True}).data["recording_id"]
    phases = set()
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            status = core.execute_tool("speech_poll", {"recording_id": token}).data
            assert status["phase"] in {"waiting", "listening", "complete"}, status
            phases.add(status["phase"])
            time.sleep(0.2)
        print("Auto device phases:", sorted(phases))
    finally:
        core.execute_tool("speech_cancel", {"recording_id": token})
    assert not core.execute_tool("speech_status", {}).data["recording"]


def test_abandoned_client_lease_discards_capture(core):
    token = core.execute_tool("speech_start", {"automatic": True}).data["recording_id"]
    try:
        time.sleep(7)
        state = core.execute_tool("speech_poll", {"recording_id": token}).data
        assert state["phase"] == "error" and "disconnected" in state["error"], state
        assert not core.execute_tool("speech_status", {}).data["recording"]
    finally:
        core.execute_tool("speech_cancel", {"recording_id": token})


def test_sapi_reports_speaking_and_actual_completion(core):
    core.execute_tool(
        "speech_speak", {"text": "JARVIS automatic conversation is ready."}
    )
    states = []
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            speaking = core.execute_tool("speech_poll", {}).data["speaking"]
            states.append(speaking)
            if True in states and not speaking:
                break
            time.sleep(0.1)
        assert True in states and states[-1] is False, states
    finally:
        core.execute_tool("speech_stop", {})
