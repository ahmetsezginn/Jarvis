# Native wake assets

Google LiteRT 2.3.0, unmodified standalone CPU `libLiteRt.dll`, Apache-2.0:
https://github.com/google-ai-edge/LiteRT
Official distribution: ai-edge-litert 2.3.0 Windows x64 wheel on PyPI. The installer extracts
only the native DLL; Python wrappers, GPU accelerators and vendor plugins are not installed.

openWakeWord, David Scripka, reference streaming feature pipeline, Apache-2.0 code:
https://github.com/dscripka/openWakeWord/tree/v0.6.0
The model artifacts come from the official v0.5.1 release and are unmodified.
The repository licenses its pretrained models CC BY-NC-SA 4.0. The underlying Google speech
embedding work is described upstream. This experimental personal setup does not establish
commercial redistribution rights for these pretrained weights.

Full license texts accompany this file. SHA256 pins are recorded in manifest.json and Rust.
