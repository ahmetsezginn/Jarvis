"""Explicit developer fixture controller. Model-driven actions still use actual Rust IPC.

No PowerShell policy change, arbitrary shell command, personal root, or existing Core shutdown.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from jarvis_brain.core.client import JarvisCoreClient
from jarvis_brain.errors import JarvisBrainError

ROOT = Path(__file__).resolve().parents[2]


def blank_pdf():
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    objects = (
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << >> /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\nendstream",
    )
    for i, item in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + item + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 5\n0000000000 65535 f \n")
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return data


def core_available():
    try:
        with JarvisCoreClient(request_timeout=1) as client:
            return client.ping() == "ok"
    except (JarvisBrainError, OSError):
        return False


def main():
    if core_available():
        raise RuntimeError(
            "A Core is already running; no existing process will be stopped"
        )
    downloads = ROOT / "target/file-context-live"
    desktop = ROOT / "target/file-context-desktop-live"
    portfolio = downloads / "cvfolder/portfolio"
    portfolio.mkdir(parents=True, exist_ok=True)
    (desktop / "Proje").mkdir(parents=True, exist_ok=True)
    (downloads / "Toplantı-Sunum.txt").write_text(
        "Synthetic meeting notes.\n", encoding="utf-8"
    )
    (portfolio / "Ahmet-Sezgin-CV-TR.pdf").write_bytes(blank_pdf())
    (desktop / "New Metin Belgesi.txt").write_text(
        "Synthetic root note.\n", encoding="utf-8"
    )
    (desktop / "Proje/uretim-notu.txt").write_text(
        "Synthetic nested note.\n", encoding="utf-8"
    )
    config = ROOT / "target/file-context-live.local.toml"
    config.write_text(
        "\n".join(
            f"[[roots]]\nname = {json.dumps(name, ensure_ascii=False)}\n"
            f"path = {json.dumps(str(path), ensure_ascii=False)}\n"
            for name, path in (("Downloads", downloads), ("Desktop", desktop))
        ),
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "JARVIS_FILES_CONFIG": str(config),
        "JARVIS_RUN_FILE_CONTEXT_LIVE": "1",
        "JARVIS_AGENT_TEST_PROFILE": "qwen35",
    }
    log = ROOT / "target/assistant-analysis/live-core-english.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as output:
        # Bootstrap only the exact repository Core host. All document/application openings
        # are issued by the test's JarvisBrain -> JarvisCoreClient -> Rust policy pipeline.
        core = subprocess.Popen(
            [str(ROOT / "target/debug/jarvis-core.exe"), "serve"],
            cwd=ROOT,
            env=environment,
            stdout=output,
            stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            deadline = time.monotonic() + 15
            while not core_available():
                if core.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(
                        "Fixture Core failed to become ready; see live-core-english.log"
                    )
                time.sleep(0.25)
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "services/brain/tests/integration/test_live_agent.py",
                    "-o",
                    "addopts=",
                    "-q",
                    "-s",
                    "--tb=short",
                    "--junitxml=target/assistant-analysis/live-agent-english.xml",
                ],
                cwd=ROOT,
                env=environment,
                check=False,
            ).returncode
        finally:
            if core.poll() is None:
                core.terminate()
                core.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
