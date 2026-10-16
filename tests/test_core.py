from contextlib import contextmanager
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen as real_urlopen
import zipfile

from voicebridge import core


def catalog_item(name="vcclient_win_cuda_v.2.2.1.zip", payload=b"zip"):
    return {"rfilename": name, "lfs": {"sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}}


def catalog(*items):
    return {"sha": "a" * 40, "siblings": list(items)}


def zip_bytes(files=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in (files or {"vcclient/start_http.bat": "@echo off\n", "vcclient/model/readme.txt": "fixture"}).items():
            z.writestr(name, content)
    return buffer.getvalue()


@contextmanager
def local_download(payload, status=200):
    """Exercise actual HTTP reads without external services or model binaries."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def redirect(req, **kwargs):
        return real_urlopen(Request(f"http://127.0.0.1:{server.server_port}/engine.zip"), **kwargs)

    try:
        with patch.object(core, "urlopen", redirect):
            yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class CatalogTests(unittest.TestCase):
    def test_only_windows_cuda_with_digest_and_size(self):
        bad_digest = catalog_item("win_cuda_v2.0.zip")
        bad_digest["lfs"]["sha256"] = "unknown"
        items = [catalog_item(), catalog_item("std_win_v2.3.0.zip"), catalog_item("cuda_mac_v2.3.0.zip"), bad_digest, catalog_item("win_cuda.zip.exe")]
        found = core.parse_catalog(catalog(*items))
        self.assertEqual([r.path for r in found], [items[0]["rfilename"]])

    def test_pins_commit_and_encodes_url(self):
        found = core.parse_catalog(catalog(catalog_item("releases/win cuda_v2.2.1.zip")))[0]
        self.assertIn("/resolve/" + "a" * 40 + "/", found.url)
        self.assertIn("win%20cuda", found.url)
        self.assertNotIn("/main/", found.url)

    def test_numeric_version_order(self):
        found = core.parse_catalog(catalog(catalog_item("win_cuda_v.2.9.0.zip"), catalog_item("win_cuda_v.2.10.0.zip")))
        self.assertIn("2.10.0", found[0].path)

    def test_excludes_5090_specific_or_experimental_builds(self):
        found = core.parse_catalog(catalog(catalog_item("win_cuda_v2.5_5090.zip"), catalog_item("win_cuda_experimental_v2.6.zip"), catalog_item()))
        self.assertEqual(len(found), 1)

    def test_invalid_revision_fails(self):
        with self.assertRaises(core.SetupError):
            core.parse_catalog({"sha": "main", "siblings": []})

    def test_unsafe_catalog_paths_and_invalid_sizes_ignored(self):
        items = [catalog_item("../win_cuda.zip"), catalog_item("/win_cuda.zip"), catalog_item("C:win_cuda.zip")]
        for size in [-1, 0, True, core.MAX_DOWNLOAD + 1, "100"]:
            item = catalog_item()
            item["lfs"]["size"] = size
            items.append(item)
        self.assertEqual(core.parse_catalog(catalog(*items)), [])

    def test_fetch_rejects_empty_catalog(self):
        with patch.object(core, "urlopen", return_value=io.BytesIO(json.dumps(catalog()).encode())):
            with self.assertRaises(core.SetupError):
                core.fetch_catalog()


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = zip_bytes()
        self.release = core.parse_catalog(catalog(catalog_item(payload=self.payload)))[0]
        self.events = []

    def progress(self, text, value):
        self.events.append((text, value))

    def test_real_http_install_and_reuse_without_redownload(self):
        with local_download(self.payload):
            launcher = core.install(self.release, self.root, self.progress)
        self.assertTrue(launcher.is_file())
        self.assertEqual(launcher.name, "start_http.bat")
        metadata = launcher.parent.parent / "voicebridge-install.json"
        self.assertEqual(json.loads(metadata.read_text())["sha256"], self.release.sha256)
        with patch.object(core, "download", side_effect=AssertionError("should reuse")):
            self.assertEqual(core.install(self.release, self.root, self.progress), launcher)
        self.assertEqual(self.events[-1][1], 100)
        self.assertFalse(list(self.root.glob("install-*")))

    def test_checksum_mismatch_preserves_previous_install(self):
        previous = self.root / "engines/previous/start_http.bat"
        previous.parent.mkdir(parents=True)
        previous.write_text("existing")
        with local_download(self.payload), self.assertRaises(core.SetupError):
            core.install(replace(self.release, sha256="0" * 64), self.root, self.progress)
        self.assertEqual(previous.read_text(), "existing")
        self.assertFalse(list(self.root.glob("install-*")))
        self.assertEqual(list((self.root / "engines").iterdir()), [previous.parent])

    @unittest.skipIf(os.name == "nt", "Windows alias handling is exercised by the real TEMP installation test")
    def test_install_through_directory_alias_reuses_resolved_launcher(self):
        real = self.root / "real-home"
        real.mkdir()
        alias = self.root / "home-alias"
        alias.symlink_to(real, target_is_directory=True)
        with local_download(self.payload):
            launcher = core.install(self.release, alias, self.progress)
        self.assertTrue(launcher.is_file())
        self.assertTrue(launcher.is_relative_to(real))
        self.assertEqual(core.install(self.release, alias, self.progress), launcher)

    def test_truncated_download_not_installed(self):
        with local_download(self.payload[:-10]), self.assertRaises(core.SetupError):
            core.install(self.release, self.root, self.progress)
        self.assertEqual(list((self.root / "engines").iterdir()), [])

    def test_oversized_download_not_installed(self):
        with local_download(self.payload + b"extra"), self.assertRaises(core.SetupError):
            core.install(self.release, self.root, self.progress)
        self.assertEqual(list((self.root / "engines").iterdir()), [])

    def test_cancel_cleans_staging(self):
        event = threading.Event()
        event.set()
        with local_download(self.payload), self.assertRaises(core.Cancelled):
            core.install(self.release, self.root, self.progress, event)
        self.assertFalse(list(self.root.glob("install-*")))

    def test_http_failure_cleans_staging(self):
        with local_download(b"not found", status=404), self.assertRaises(Exception) as caught:
            core.install(self.release, self.root, self.progress)
        self.assertIn("404", str(caught.exception))
        self.assertFalse(list(self.root.glob("install-*")))

    def test_missing_launcher_never_commits_install(self):
        payload = zip_bytes({"unrelated.exe": "not a launcher"})
        release = core.parse_catalog(catalog(catalog_item(payload=payload)))[0]
        with local_download(payload), self.assertRaises(core.SetupError):
            core.install(release, self.root, self.progress)
        self.assertEqual(list((self.root / "engines").iterdir()), [])

    def test_low_disk_fails_before_network(self):
        with patch.object(core.shutil, "disk_usage", return_value=type("Disk", (), {"free": 10})()), patch.object(core, "download") as mocked:
            with self.assertRaises(core.SetupError):
                core.install(self.release, self.root, self.progress)
        mocked.assert_not_called()


class ArchiveTests(unittest.TestCase):
    def test_reject_windows_unsafe_paths(self):
        for name in ["../escape", "/absolute", "C:/escape", "..\\escape", "dir/file:stream", "dir/NUL.txt", "dir/foo.", "dir/foo ", "dir/COM1", "dir/a?.txt"]:
            with self.subTest(name=name), self.assertRaises(core.SetupError):
                core.safe_member(zipfile.ZipInfo(name))

    def test_reject_symlink(self):
        info = zipfile.ZipInfo("linked")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(core.SetupError):
            core.safe_member(info)

    def test_duplicate_windows_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "fixture.zip"
            archive.write_bytes(zip_bytes({"File.txt": "one", "file.txt": "two"}))
            with self.assertRaises(core.SetupError):
                core.extract_archive(archive, root / "output", lambda *_: None)
            self.assertFalse((root / "output").exists())

    def test_traversal_validated_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "fixture.zip"
            archive.write_bytes(zip_bytes({"good/file": "ok", "../escape": "bad"}))
            with self.assertRaises(core.SetupError):
                core.extract_archive(archive, root / "output", lambda *_: None)
            self.assertFalse((root / "output").exists())
            self.assertFalse((root / "escape").exists())

    def test_expansion_limit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(core, "MAX_EXPANDED", 1):
            root = Path(directory)
            archive = root / "fixture.zip"
            archive.write_bytes(zip_bytes())
            with self.assertRaises(core.SetupError):
                core.extract_archive(archive, root / "output", lambda *_: None)

    def test_ambiguous_installations_require_explicit_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for sub in ["a", "b"]:
                (root / sub).mkdir()
                (root / sub / "start_http.bat").touch()
            with self.assertRaises(core.SetupError):
                core.find_launcher(root)


class ConfigurationTests(unittest.TestCase):
    def test_atomic_save_and_corrupt_config_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            core.save_config(home, {"launcher": "C:/ses/start_http.bat", "language": "Türkçe"})
            self.assertEqual(core.read_config(home)["language"], "Türkçe")
            self.assertFalse(list(home.glob("*.tmp")))
            (home / "settings.json").write_text("broken")
            self.assertEqual(core.read_config(home), {})

    def test_gpu_diagnosis_missing_tool_is_actionable(self):
        with patch.object(core.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIn("NVIDIA sürücüsünü", core.gpu_report())

    @unittest.skipUnless(os.name == "nt", "Windows batch execution requires Windows")
    def test_windows_batch_launch_in_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="voice bridge ") as directory:
            home = Path(directory)
            batch = home / "start_http.bat"
            batch.write_text('@echo off\necho launched>ready.txt\n', encoding="ascii")
            process = core.launch(batch)
            self.assertEqual(process.wait(timeout=15), 0)
            self.assertEqual((home / "ready.txt").read_text().strip(), "launched")


if __name__ == "__main__":
    unittest.main()
