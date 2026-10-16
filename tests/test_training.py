import array
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch
import wave

from voicebridge import training, core


@unittest.skipUnless(shutil.which("ffmpeg"), "Dataset integration test requires FFmpeg")
class PreparationTests(unittest.TestCase):
    def test_prepares_bounded_mono_clips_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "reference.wav"
            samples = array.array("h", [1000, -1000] * (16000 * 13 // 2))
            with wave.open(str(source), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(samples.tobytes())
            before = source.read_bytes()
            data = training.prepare(source, root / "work")
            report = json.loads((root / "work/status.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "prepared_not_trained")
            self.assertEqual(report["completed_steps"], 0)
            self.assertGreaterEqual(report["total_seconds"], 12)
            for path in data.glob("*.wav"):
                with wave.open(str(path), "rb") as handle:
                    self.assertEqual(handle.getnchannels(), 1)
                    self.assertEqual(handle.getframerate(), 22050)
                    self.assertGreaterEqual(handle.getnframes() / handle.getframerate(), 1)
                    self.assertLess(handle.getnframes() / handle.getframerate(), 6.1)
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue((root / "work/reference.wav").is_file())
            with self.assertRaises(FileExistsError):
                training.prepare(source, root / "work")

    def test_no_data_fails_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "empty"
            source.mkdir()
            with self.assertRaises(core.SetupError):
                training.prepare(source, root / "work")
            self.assertFalse((root / "work").exists())


class FailureReportingTests(unittest.TestCase):
    def test_model_loading_failure_records_zero_steps_and_restores_cwd(self):
        import os
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / "engine"
            config = engine / training.CONFIG
            config.parent.mkdir(parents=True)
            config.write_text("{}")
            work = root / "work"
            work.mkdir()
            training.write_report(work / "status.json", {"status": "prepared_not_trained", "completed_steps": 0})
            fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
            fake_train = types.SimpleNamespace(Trainer=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("download denied")))
            fake_yaml = types.SimpleNamespace(safe_load=lambda _: {}, safe_dump=lambda _: "{}")
            previous = Path.cwd()
            with patch.dict('sys.modules', {"torch": fake_torch, "train": fake_train, "yaml": fake_yaml}):
                with self.assertRaisesRegex(RuntimeError, "download denied"):
                    training.train(engine, work, 100, "cpu")
            self.assertEqual(Path.cwd(), previous)
            status = json.loads((work / "status.json").read_text())
            self.assertEqual(status["status"], "training_failed")
            self.assertEqual(status["completed_steps"], 0)
            self.assertFalse((work / "runs/DogalKadinTR/ft_model.pth").exists())


if __name__ == "__main__":
    unittest.main()
