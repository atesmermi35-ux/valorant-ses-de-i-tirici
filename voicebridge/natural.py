"""Local, file-based OpenVoice V2 feminine-tone preview. No cloud audio upload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

from . import core, training

REVISION = "f36e7edfe1684461a8343844af60babc2efbb727"
REFERENCE_HASH = "4d2bd83ff0f7fe33491b03193abdf623f1b4cc2d8103972b33638d3607d86dc5"


def convert(source: Path, output: Path, engine: Path, pitch: str = "auto") -> dict:
    source = source.resolve(strict=True)
    output = output.resolve()
    engine = engine.resolve(strict=True)
    if output.exists():
        raise core.SetupError("Çıktı zaten var; başka bir dosya adı seç.")
    if output.with_suffix(".json").exists():
        raise core.SetupError("Bu adla bir rapor dosyası zaten var; başka bir çıktı adı seç.")
    reference = Path(__file__).resolve().parent.parent / "assets/voices/LJ001-0001.wav"
    if hashlib.sha256(reference.read_bytes()).hexdigest() != REFERENCE_HASH:
        raise core.SetupError("Referans ses dosyasının SHA-256 değeri uyuşmuyor.")
    import numpy as np
    import librosa
    import soundfile as sf
    import torch
    from huggingface_hub import hf_hub_download
    sys.path.insert(0, str(engine))
    try:
        from modules.openvoice.api import ToneColorConverter
        cache = str(engine / "checkpoints")
        config = hf_hub_download("myshell-ai/OpenVoiceV2", "converter/config.json", revision=REVISION, cache_dir=cache)
        weights = hf_hub_download("myshell-ai/OpenVoiceV2", "converter/checkpoint.pth", revision=REVISION, cache_dir=cache)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        converter = ToneColorConverter(config, device=device)
        converter.load_ckpt(weights)
        samples, _ = librosa.load(source, sr=22050, mono=True)
        target, _ = librosa.load(reference, sr=22050, mono=True)
        if samples.size < 22050 or not np.isfinite(samples).all() or np.max(np.abs(samples)) < 1e-5:
            raise core.SetupError("Kaynak en az bir saniyelik, geçerli ve duyulabilir ses içermeli.")
        shift = 0.0
        if pitch == "auto":
            # Match acoustic register without assigning a gender to the user.
            def median_f0(audio):
                f0, voiced, probability = librosa.pyin(audio[:22050 * 10], sr=22050, fmin=65, fmax=450)
                valid = f0[np.isfinite(f0) & voiced & (probability > 0.5)]
                return float(np.median(valid)) if len(valid) >= 5 else None
            input_f0, target_f0 = median_f0(samples), median_f0(target)
            if input_f0 and target_f0:
                shift = float(np.clip(12 * np.log2(target_f0 / input_f0), 0, 6))
                if shift < 2:
                    shift = 0.0
            if shift:
                samples = librosa.effects.pitch_shift(samples, sr=22050, n_steps=shift)
        def tensor(audio):
            return torch.from_numpy(audio).unsqueeze(0).to(device), torch.tensor([len(audio)], device=device)
        target_tensor, target_length = tensor(target)
        torch.manual_seed(0)
        with torch.inference_mode():
            target_embedding = converter.extract_se(target_tensor, target_length)
            # Overlap chunks so long files do not exhaust 4GB GPU memory.
            block, overlap = 22050 * 6, 2205
            pieces = []
            for start in range(0, len(samples), block - overlap):
                part = samples[start:start + block]
                if len(part) < 512:
                    break
                wave, length = tensor(part)
                source_embedding = converter.extract_se(wave, length)
                converted = converter.convert(wave, length, source_embedding, target_embedding).squeeze().cpu().numpy()
                if len(converted) < len(part):
                    converted = np.pad(converted, (0, len(part) - len(converted)))
                converted = converted[:len(part)]
                if pieces:
                    n = min(overlap, len(pieces[-1]), len(converted))
                    ramp = np.linspace(0, 1, n, dtype=np.float32)
                    pieces[-1][-n:] = pieces[-1][-n:] * (1 - ramp) + converted[:n] * ramp
                    converted = converted[n:]
                pieces.append(converted)
                if start + block >= len(samples):
                    break
            result = np.concatenate(pieces)
        if not np.isfinite(result).all() or np.max(np.abs(result)) < 1e-6:
            raise core.SetupError("Dönüşüm geçerli bir ses çıktısı oluşturmadı.")
        if abs(len(result) - len(samples)) > 512:
            raise core.SetupError("Dönüşüm süresi beklenmedik ölçüde değişti.")
        # Retain headroom instead of clipping when conversion peaks exceed 1.
        peak = float(np.max(np.abs(result)))
        if peak > 0.98:
            result = result * (0.98 / peak)
        output.parent.mkdir(parents=True, exist_ok=True)
        sf.write(output, result, 22050, subtype="PCM_16")
        info = {"engine": "OpenVoiceV2", "revision": REVISION, "reference": "LJ Speech LJ001-0001",
                "device": device, "pitch_shift_semitones": shift, "seconds": len(result) / 22050,
                "validation": "Signal health only; naturalness and intelligibility need listening."}
        output.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        return info
    finally:
        if sys.path and sys.path[0] == str(engine):
            sys.path.pop(0)


def local():
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        raise core.SetupError("Otomatik kurulum Windows ve Python 3.12 gerektirir.")
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        source = filedialog.askopenfilename(title="Dönüştürmek istediğin kendi ses kaydını seç", filetypes=[("Ses kaydı", "*.wav *.mp3 *.flac *.ogg *.m4a")], initialdir=r"C:\Axtenix\SesVerisi")
        if not source:
            return
        output = filedialog.asksaveasfilename(title="Sonuç WAV dosyasını kaydet", defaultextension=".wav", initialfile="dogal-kadin-deneme.wav")
        if not output:
            return
        if Path(output).exists():
            raise core.SetupError("Mevcut dosyanın üzerine yazılmayacak; yeni bir çıktı adı seç.")
    finally:
        root.destroy()
    home = core.app_home() / "natural"
    environment = home / "python312"
    python = environment / "Scripts/python.exe"
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    print("CPU ses denemesi hazırlanıyor. İlk kurulum yüzlerce MB indirebilir.", flush=True)
    subprocess.run([str(python), "-m", "pip", "install", "torch==2.4.0+cpu", "torchaudio==2.4.0+cpu", "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    project = Path(__file__).resolve().parent.parent
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(project / "requirements-natural.txt")], check=True)
    engine = training.engine_source(home)
    subprocess.run([str(python), "-m", "voicebridge.natural", "convert", "--source", source, "--output", output, "--engine", str(engine)], cwd=project, check=True)
    print("Deneme kaydı hazır:", output)
    os.startfile(output)


def main():
    parser = argparse.ArgumentParser(description="Doğal kadın sesi için yerel kayıt dönüşümü denemesi")
    parser.add_argument("action", choices=["local", "convert"])
    for name in ["source", "output", "engine"]:
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--pitch", choices=["auto", "none"], default="auto")
    args = parser.parse_args()
    try:
        if args.action == "local":
            local()
        else:
            if not all([args.source, args.output, args.engine]):
                parser.error("Kaynak, çıktı ve motor klasörü gerekli.")
            print(json.dumps(convert(args.source, args.output, args.engine, args.pitch), ensure_ascii=False))
    except Exception as exc:
        parser.exit(1, f"Deneme tamamlanmadı: {exc}\n")


if __name__ == "__main__":
    main()
