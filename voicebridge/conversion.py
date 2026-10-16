"""File-based quality check of a Seed-VC checkpoint, separate from live audio."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


def convert(engine: Path, checkpoint: Path, config: Path, source: Path, reference: Path, output: Path):
    engine = engine.resolve(strict=True)
    checkpoint = checkpoint.resolve(strict=True)
    config = config.resolve(strict=True)
    source = source.resolve(strict=True)
    reference = reference.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Çıktı dosyası zaten var; farklı bir ad seç.")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Set caches before Transformers/HF imports; the cloud HOME is read-only.
    os.environ.setdefault("HF_HUB_CACHE", str(engine / "checkpoints/hf_cache"))
    os.environ.setdefault("MPLCONFIGDIR", str(output.parent / ".cache/matplotlib"))
    import torch
    import soundfile as sf
    import numpy as np
    from transformers import WhisperModel
    loader = WhisperModel.from_pretrained

    def load_whisper(*args, **kwargs):
        # Upstream inference hardcodes float16 for Whisper even on CPU.
        if not torch.cuda.is_available() and not torch.backends.mps.is_available():
            kwargs["torch_dtype"] = torch.float32
        return loader(*args, **kwargs)

    previous = Path.cwd()
    try:
        os.chdir(engine)
        sys.path.insert(0, str(engine))
        import inference
        with tempfile.TemporaryDirectory(prefix="voice-check-", dir=output.parent) as directory:
            args = argparse.Namespace(source=str(source), target=str(reference), output=directory,
                                      checkpoint=str(checkpoint), config=str(config), diffusion_steps=50,
                                      inference_cfg_rate=0.7, length_adjust=1.0, f0_condition=False,
                                      auto_f0_adjust=False, semi_tone_shift=0, fp16=torch.cuda.is_available())
            # Scope the upstream compatibility override to this conversion only.
            with patch.object(WhisperModel, "from_pretrained", side_effect=load_whisper):
                inference.main(args)
            files = list(Path(directory).glob("*.wav"))
            if len(files) != 1:
                raise RuntimeError("Tek bir dönüşüm WAV çıktısı bekleniyordu.")
            samples, rate = sf.read(files[0], dtype="float32")
            if not samples.size or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 1e-6:
                raise RuntimeError("Dönüşüm boş, geçersiz veya tamamen sessiz çıktı üretti.")
            samples_source, source_rate = sf.read(source)
            expected = len(samples_source) / source_rate
            duration = len(samples) / rate
            if abs(duration - expected) > max(0.5, expected * 0.1):
                raise RuntimeError("Dönüşüm süresi kaynak süresinden beklenmedik ölçüde farklı.")
            files[0].rename(output)
            return {"output": str(output), "sample_rate": rate, "seconds": duration,
                    "peak": float(np.max(np.abs(samples))), "source_seconds": expected,
                    "validation": "Signal health and duration only; Turkish intelligibility and naturalness require listening."}
    finally:
        os.chdir(previous)
        if sys.path and sys.path[0] == str(engine):
            sys.path.pop(0)


def main():
    parser = argparse.ArgumentParser(description="Seed-VC kalite öncelikli kayıt dönüşümü")
    for name in ["engine", "checkpoint", "config", "source", "reference", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = convert(**vars(args))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        parser.exit(1, f"Dönüşüm tamamlanmadı: {exc}\n")


if __name__ == "__main__":
    main()
