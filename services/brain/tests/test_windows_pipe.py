import sys

import pytest

from jarvis_brain.ipc.windows_pipe import current_user_pipe_endpoint, current_user_sid


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Named Pipe contract")
def test_current_user_pipe_endpoint_is_stable_and_sid_scoped() -> None:
    sid = current_user_sid()
    assert sid.startswith("S-1-")
    assert current_user_pipe_endpoint() == rf"\\.\pipe\jarvis-core-{sid}-v1"
