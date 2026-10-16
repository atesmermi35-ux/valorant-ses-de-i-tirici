"""Prepare private speech data and fine-tune the separate Seed-VC engine.

This adapter does not invent trained weights. A successful training run must
produce ft_model.pth and a status report with completed optimizer steps.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import venv
import wave

from . import core

COMMIT = "51383efd921027683c89e5348211d93ff12ac2a8"
SOURCE_SHA256 = "72a27a1d20efec1489041eac2854e3e1c9c23d650ac15900821ad3ab367f0290"
CONFIG = "configs/presets/config_dit_mel_seed_uvit_whisper_small_wavenet.yml"
FORMATS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".opus"}


def write_report(path: Path, value: dict):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def ffmpeg_program() -> str:
    program = shutil.which("ffmpeg")
    if program:
        return program
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def prepare(source: Path, work: Path) -> Path:
    """Make 1–6s PCM clips without changing originals or asserting voice quality."""
    source = source.resolve(strict=True)
    inputs = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.suffix.lower() in FORMATS and p.is_file())
    if not inputs or any(p.suffix.lower() not in FORMATS for p in inputs):
        raise core.SetupError("MP3/WAV/FLAC/OGG/M4A/OPUS ses kaydı bulunamadı.")
    work = work.resolve()
    if work == source or (source.is_dir() and source in work.parents):
        raise core.SetupError("Çıktı klasörü kaynak kayıtların içinde olmamalı.")
    work.mkdir(parents=True, exist_ok=False)
    data = work / "dataset"
    data.mkdir()
    manifest = {"status": "preparing", "engine": "Seed-VC", "engine_commit": COMMIT, "config": CONFIG,
                "completed_steps": 0, "sources": [], "clips": [], "reference": "reference.wav",
                "review": "Only technical preparation. Music, overlapping speakers and perceptual naturalness require listening.",
                "quality_inference": {"diffusion_steps": 50, "inference_cfg_rate": 0.7, "length_adjust": 1.0, "f0_condition": False}}
    report = work / "status.json"
    write_report(report, manifest)
    try:
        program = ffmpeg_program()
        for number, path in enumerate(inputs):
            with path.open("rb") as handle:
                source_digest = hashlib.file_digest(handle, "sha256").hexdigest()
            manifest["sources"].append({"file": path.name, "sha256": source_digest})
            command = [program, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(path),
                       "-map", "0:a:0", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le",
                       "-f", "segment", "-segment_time", "6", "-reset_timestamps", "1", str(data / f"source{number:03d}_%04d.wav")]
            subprocess.run(command, check=True, capture_output=True)
        for path in sorted(data.glob("*.wav")):
            with wave.open(str(path), "rb") as handle:
                duration = handle.getnframes() / handle.getframerate()
            if duration < 1:
                path.unlink()  # Only our generated sub-second tail; originals untouched.
                continue
            manifest["clips"].append({"file": path.name, "seconds": duration})
        if not manifest["clips"]:
            raise core.SetupError("Bir saniyeden uzun eğitim parçası çıkmadı.")
        subprocess.run([program, "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-i", str(inputs[0]),
                        "-t", "15", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(work / "reference.wav")], check=True, capture_output=True)
        manifest["status"] = "prepared_not_trained"
        manifest["total_seconds"] = sum(item["seconds"] for item in manifest["clips"])
        write_report(report, manifest)
        return data
    except Exception as exc:
        manifest.update(status="preparation_failed", error=str(exc))
        write_report(report, manifest)
        raise


def engine_source(home: Path) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    final = home / f"seed-vc-{COMMIT}"
    if (final / "train.py").is_file():
        return final
    if final.exists():
        raise core.SetupError("Eksik Seed-VC kaynak klasörü bulundu; mevcut dosyaların üzerine yazılmadı.")
    with tempfile.TemporaryDirectory(prefix="seed-source-", dir=home) as directory:
        temp = Path(directory)
        archive = temp / "source.zip"
        with urlopen(f"https://codeload.github.com/Plachtaa/seed-vc/zip/{COMMIT}", timeout=60) as response, archive.open("wb") as output:
            digest = hashlib.sha256()
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > 100 * 1024**2:
                    raise core.SetupError("Kaynak arşivi beklenen boyutu aştı.")
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != SOURCE_SHA256:
            raise core.SetupError("Seed-VC kaynak arşivinin SHA-256 değeri uyuşmadı.")
        core.extract_archive(archive, temp / "source", lambda *_: None)
        source = temp / "source" / f"seed-vc-{COMMIT}"
        if not (source / CONFIG).is_file() or not (source / "train.py").is_file():
            raise core.SetupError("Seed-VC kaynak yapısı beklenenden farklı.")
        source.rename(final)
    return final


def train(engine: Path, work: Path, steps: int, device: str):
    """Use the upstream Trainer's explicit device argument, keeping source intact."""
    import torch
    if device == "cuda" and not torch.cuda.is_available():
        raise core.SetupError("CUDA GPU kullanılamıyor. NVIDIA sürücüsünü ve CUDA PyTorch kurulumunu kontrol et.")
    engine = engine.resolve(strict=True)
    work = work.resolve(strict=True)
    report = work / "status.json"
    state = json.loads(report.read_text(encoding="utf-8"))
    if state.get("status") not in {"prepared_not_trained", "training_failed"}:
        raise core.SetupError("Bu çalışma yeni veya yeniden denenebilir hazırlanmış veri içermiyor.")
    state.update(status="loading_model", requested_steps=steps, device=device, completed_steps=0)
    write_report(report, state)
    previous = Path.cwd()
    try:
        os.environ.setdefault("MPLCONFIGDIR", str(work / ".cache/matplotlib"))
        os.chdir(engine)
        sys.path.insert(0, str(engine))
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from train import Trainer
        import yaml
        config = yaml.safe_load((engine / CONFIG).read_text(encoding="utf-8"))
        config["log_dir"] = str(work / "runs")
        config["log_interval"] = 1
        configuration = work / "seed-quality.yml"
        configuration.write_text(yaml.safe_dump(config), encoding="utf-8")
        trainer = Trainer(config_path=str(configuration), pretrained_ckpt_path=None,
                          data_dir=str(work / "dataset"), run_name="DogalKadinTR", batch_size=1,
                          num_workers=0, steps=steps, save_interval=min(steps, 50), max_epochs=max(1000, steps), device=device)
        original_step = trainer.train_one_step

        def recorded_step(*args, **kwargs):
            loss = original_step(*args, **kwargs)
            state.update(status="training", completed_steps=state["completed_steps"] + 1, last_loss=float(loss))
            write_report(report, state)
            return loss

        trainer.train_one_step = recorded_step
        trainer.train()
        checkpoint = work / "runs/DogalKadinTR/ft_model.pth"
        if not checkpoint.is_file() or state["completed_steps"] < steps:
            raise core.SetupError("Eğitim gerekli adımları veya çıktı dosyasını tamamlamadı.")
        state.update(status="trained_not_listening_validated", checkpoint=str(checkpoint))
        write_report(report, state)
    except Exception as exc:
        state.update(status="training_failed", error=str(exc))
        write_report(report, state)
        raise
    finally:
        os.chdir(previous)
        if sys.path and sys.path[0] == str(engine):
            sys.path.pop(0)


def local_setup():
    """On Windows, prepare an isolated runtime and use user-selected local data."""
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        raise core.SetupError("Bu otomatik eğitim kurulumu Windows ve Python 3.12 gerektirir.")
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    source = filedialog.askdirectory(title="Tek kadın konuşmacıya ait temiz ses kayıtlarının klasörünü seç", initialdir=r"C:\Axtenix\SesVerisi")
    root.destroy()
    if not source:
        print("Klasör seçilmedi; eğitim başlatılmadı.")
        return
    home = core.app_home() / "training"
    environment = home / "python312"
    python = environment / "Scripts/python.exe"
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(environment)
    print("Ayrı eğitim ortamı kuruluyor; birkaç GB indirilebilir. Mevcut Python paketleri değiştirilmez.", flush=True)
    subprocess.run([str(python), "-m", "pip", "install", "torch==2.4.0+cu118", "torchaudio==2.4.0+cu118", "--index-url", "https://download.pytorch.org/whl/cu118"], check=True)
    requirements = Path(__file__).resolve().parent.parent / "requirements-model.txt"
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(requirements)], check=True)
    engine = engine_source(home)
    work = home / ("DogalKadinTR-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    command = [str(python), "-m", "voicebridge.training", "run", "--source", source, "--work", str(work), "--engine", str(engine), "--steps", "100", "--device", "cuda"]
    subprocess.run(command, cwd=requirements.parent, check=True)
    print("Eğitim tamamlandı. Türkçe anlaşılırlık ve doğal ses dinleme testi hâlâ gerekli.")


def main():
    parser = argparse.ArgumentParser(description="Seed-VC: kalite öncelikli kadın sesi hazırlığı ve eğitimi")
    parser.add_argument("action", choices=["prepare", "run", "local"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--work", type=Path)
    parser.add_argument("--engine", type=Path)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    args = parser.parse_args()
    try:
        if args.action == "local":
            local_setup()
            return
        if not args.source or not args.work or (args.action == "run" and not args.engine) or args.steps < 1:
            parser.error("Kaynak, yeni çalışma klasörü ve eğitim için motor klasörü gerekli; adım sayısı pozitif olmalı.")
        prepare(args.source, args.work)
        print("Ses verisi hazır:", args.work, flush=True)
        if args.action == "run":
            train(args.engine, args.work, args.steps, args.device)
    except Exception as exc:
        parser.exit(1, f"İşlem tamamlanmadı: {exc}\n")


if __name__ == "__main__":
    main()
