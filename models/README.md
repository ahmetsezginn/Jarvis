# Generated local models

Model weights are provisioned artifacts and are not committed to Git. Run
`scripts/models/build_qwen3_int4.ps1` to populate `qwen3-0.6b-int4/` from the pinned upstream
Qwen revision. Provisioning copies the Apache-2.0 license and writes `MODEL_MANIFEST.json` with
the conversion settings, measured artifact size, and per-file SHA-256 checksums.
