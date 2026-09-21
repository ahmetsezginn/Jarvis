# Qwen3-0.6B INT4 provisioning

The production Brain never downloads a model. Provisioning is an explicit, separate build step.
The script uses the supported ONNX Runtime GenAI 0.15.2 model builder from its wheel, downloads
the exact Qwen source revision recorded below into a conversion-only environment, targets INT4
CPU, verifies that the result loads, and writes checksums to `MODEL_MANIFEST.json`.

```powershell
.\scripts\models\build_qwen3_int4.ps1
```

Pinned inputs:

- model: `Qwen/Qwen3-0.6B`
- revision: `c1899de289a04d12100db370d81485cdf75e47ca`
- runtime/builder: `onnxruntime-genai==0.15.2`
- provider/precision: `CPUExecutionProvider`, symmetric INT4, block size 32

PyTorch, Transformers and the downloader exist only under `.model-build` and are absent from the
production dependency list. The source and conversion caches are ignored by Git. The generated
model weights are also ignored; deploy the verified artifact directory separately.

After a successful first build, capture the resolved conversion environment with:

```powershell
.\scripts\models\.model-build\Scripts\python.exe -m pip freeze |
    Set-Content .\scripts\models\requirements-build.lock
```

`verify_qwen3_int4.py` can be run independently against an artifact and loads it on CPU before
reporting per-file SHA-256 hashes and its measured total size.
