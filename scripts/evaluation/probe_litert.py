"""File-only official native LiteRT compatibility/score check; no microphone or activation."""

import array
import ctypes as c
import json
import time
import wave
from pathlib import Path


class Runtime:
    def __init__(self, path):
        self.dll = c.CDLL(str(path.resolve()))
        p = c.c_void_p
        for name, result, arguments in [
            ("TfLiteModelCreate", p, [p, c.c_size_t]),
            ("TfLiteModelDelete", None, [p]),
            ("TfLiteInterpreterOptionsCreate", p, []),
            ("TfLiteInterpreterOptionsSetNumThreads", None, [p, c.c_int]),
            ("TfLiteInterpreterOptionsDelete", None, [p]),
            ("TfLiteInterpreterCreate", p, [p, p]),
            ("TfLiteInterpreterDelete", None, [p]),
            (
                "TfLiteInterpreterResizeInputTensor",
                c.c_int,
                [p, c.c_int, c.POINTER(c.c_int), c.c_int],
            ),
            ("TfLiteInterpreterAllocateTensors", c.c_int, [p]),
            ("TfLiteInterpreterGetInputTensor", p, [p, c.c_int]),
            ("TfLiteInterpreterGetOutputTensor", p, [p, c.c_int]),
            ("TfLiteTensorByteSize", c.c_size_t, [p]),
            ("TfLiteTensorCopyFromBuffer", c.c_int, [p, p, c.c_size_t]),
            ("TfLiteTensorCopyToBuffer", c.c_int, [p, p, c.c_size_t]),
            ("TfLiteInterpreterInvoke", c.c_int, [p]),
        ]:
            f = getattr(self.dll, name)
            f.restype, f.argtypes = result, arguments

    def model(self, path, shape):
        return Model(self, path, shape)


class Model:
    def __init__(self, runtime, path, shape):
        self.runtime = runtime
        self.bytes = c.create_string_buffer(path.read_bytes())
        d = runtime.dll
        self.model = d.TfLiteModelCreate(self.bytes, len(self.bytes) - 1)
        assert self.model
        options = d.TfLiteInterpreterOptionsCreate()
        d.TfLiteInterpreterOptionsSetNumThreads(options, 1)
        self.interpreter = d.TfLiteInterpreterCreate(self.model, options)
        d.TfLiteInterpreterOptionsDelete(options)
        assert self.interpreter
        assert (
            d.TfLiteInterpreterResizeInputTensor(
                self.interpreter, 0, (c.c_int * len(shape))(*shape), len(shape)
            )
            == 0
        )
        assert d.TfLiteInterpreterAllocateTensors(self.interpreter) == 0
        self.input = d.TfLiteInterpreterGetInputTensor(self.interpreter, 0)
        self.output = d.TfLiteInterpreterGetOutputTensor(self.interpreter, 0)

    def run(self, values):
        d = self.runtime.dll
        values = array.array("f", values)
        ptr, length = values.buffer_info()
        assert d.TfLiteTensorByteSize(self.input) == length * 4
        assert d.TfLiteTensorCopyFromBuffer(self.input, ptr, length * 4) == 0
        assert d.TfLiteInterpreterInvoke(self.interpreter) == 0
        output = c.create_string_buffer(d.TfLiteTensorByteSize(self.output))
        assert d.TfLiteTensorCopyToBuffer(self.output, output, len(output)) == 0
        values = array.array("f")
        values.frombytes(output.raw)
        return list(values)

    def close(self):
        self.runtime.dll.TfLiteInterpreterDelete(self.interpreter)
        self.runtime.dll.TfLiteModelDelete(self.model)


def main():
    root = Path(__file__).resolve().parents[2]
    runtime = Runtime(root / "target/wake-provider/litert/libLiteRt.dll")
    models = root / "target/wake-provider/tflite"
    mel = runtime.model(models / "melspectrogram.tflite", [1, 1760])
    embedding = runtime.model(models / "embedding_model.tflite", [1, 76, 32, 1])
    keyword = runtime.model(models / "hey_jarvis_v0.1.tflite", [1, 16, 96])
    results = []
    try:
        for file in sorted((root / "target/wake-fixtures").glob("*.wav")):
            with wave.open(str(file), "rb") as wav:
                assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
                rate = wav.getframerate()
                raw = array.array("h", wav.readframes(wav.getnframes()))
            pcm = (
                [0] * 16000
                + [raw[i * rate // 16000] for i in range(len(raw) * 16000 // rate)]
                + [0] * 16000
            )
            mels = [1.0] * (76 * 32)
            features = embedding.run(mels) * 16
            previous = [0] * 480
            maximum = 0.0
            started = time.perf_counter()
            for index in range(0, len(pcm) - 1280 + 1, 1280):
                frame = previous + pcm[index : index + 1280]
                previous = frame[-480:]
                mels = (mels + [x / 10 + 2 for x in mel.run(frame)])[-76 * 32 :]
                features = (features + embedding.run(mels))[-16 * 96 :]
                maximum = max(maximum, keyword.run(features)[0])
            results.append(
                {
                    "file": file.name,
                    "expected": file.name.startswith("wake-"),
                    "score": maximum,
                    "detected": maximum >= 0.5,
                    "decode_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
    finally:
        for model in [keyword, embedding, mel]:
            model.close()
    (root / "target/wake-litert-evaluation.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results, indent=2))
    raise SystemExit(
        0 if all(row["detected"] == row["expected"] for row in results) else 1
    )


if __name__ == "__main__":
    main()
