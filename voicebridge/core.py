"""Dependency-free installer for official w-okada VCClient Windows ZIPs.

Never import or execute downloaded code here. Execution is a separate user action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import threading
from typing import Callable
from urllib.parse import quote
from urllib.request import Request, urlopen
import zipfile


REPOSITORY = "wok000/vcclient000"
OFFICIAL_DOWNLOADS = f"https://huggingface.co/{REPOSITORY}/tree/main"
UPSTREAM = "https://github.com/w-okada/voice-changer"
VIRTUAL_CABLE = "https://vb-audio.com/Cable/"
USER_AGENT = "VoiceBridge/0.1 (+https://github.com/atesmermi35-ux/valorant-ses-de-i-tirici)"
MAX_DOWNLOAD = 16 * 1024**3
MAX_EXPANDED = 32 * 1024**3
LAUNCHERS = ("start_http.bat", "vcclient.exe")


class SetupError(Exception):
    """An actionable installation failure."""


class Cancelled(SetupError):
    pass


@dataclass(frozen=True)
class Release:
    path: str
    revision: str
    sha256: str
    size: int

    @property
    def label(self) -> str:
        return f"{PurePosixPath(self.path).name}  ({self.size / 1024**3:.2f} GB)"

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{REPOSITORY}/resolve/{self.revision}/{quote(self.path, safe='/')}"


def app_home() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "VoiceBridge"
    return Path.home() / ".local/share/voicebridge"


def read_config(home: Path) -> dict:
    try:
        value = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(home: Path, config: dict) -> None:
    home.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=home)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        os.replace(name, home / "settings.json")
    finally:
        Path(name).unlink(missing_ok=True)


def _version(path: str) -> tuple[int, ...]:
    match = re.search(r"v[._-]?(\d+(?:[._]\d+){1,3})", path.lower())
    return tuple(map(int, re.split(r"[._]", match[1]))) if match else ()


def parse_catalog(data: dict) -> list[Release]:
    """Pin each artifact to the repo commit and the publisher's LFS SHA-256."""
    revision = data.get("sha", "")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise SetupError("Resmî indirme kataloğunun sürüm kimliği doğrulanamadı.")
    releases = []
    for item in data.get("siblings", []):
        path = item.get("rfilename", "")
        lower = path.lower()
        # CUDA Windows builds support RVC. Do not silently choose std (Beatrice only).
        if not (lower.endswith(".zip") and "win" in lower and "cuda" in lower):
            continue
        if "5090" in lower or "experimental" in lower:
            continue
        parts = PurePosixPath(path).parts
        if ".." in parts or PurePosixPath(path).is_absolute() or "\\" in path or ":" in path:
            continue
        lfs = item.get("lfs") or {}
        digest = lfs.get("sha256", lfs.get("oid", ""))
        if isinstance(digest, str):
            digest = digest.removeprefix("sha256:")
        size = lfs.get("size", item.get("size"))
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            continue
        if type(size) is not int or not 0 < size <= MAX_DOWNLOAD:
            continue
        releases.append(Release(path, revision, digest, size))
    # Default to newest CUDA ZIP, keeping older versions available explicitly.
    return sorted(releases, key=lambda r: (_version(r.path), r.path), reverse=True)


def fetch_catalog() -> list[Release]:
    req = Request(f"https://huggingface.co/api/models/{REPOSITORY}?blobs=true", headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as response:
        data = json.load(response)
    releases = parse_catalog(data)
    if not releases:
        raise SetupError("Katalogda SHA-256 bilgisi olan Windows CUDA ZIP bulunamadı. Resmî indirme sayfasını kullanıp çıkardığın klasörü seçebilirsin.")
    return releases


def _cancel(event: threading.Event | None) -> None:
    if event and event.is_set():
        raise Cancelled("İşlem iptal edildi; mevcut kurulum korundu.")


def download(release: Release, target: Path, progress: Callable[[str, float], None], cancel: threading.Event | None = None) -> None:
    """Stream into a partial file; a mismatch never produces an installable ZIP."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    partial.unlink(missing_ok=True)
    try:
        req = Request(release.url, headers={"User-Agent": USER_AGENT})
        digest = hashlib.sha256()
        received = 0
        with urlopen(req, timeout=45) as response, partial.open("xb") as handle:
            while True:
                _cancel(cancel)
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > release.size:
                    raise SetupError("İndirilen dosya beklenen boyutu aşıyor.")
                digest.update(chunk)
                handle.write(chunk)
                progress(f"İndiriliyor: {received / 1024**2:.0f} / {release.size / 1024**2:.0f} MB", received / release.size * 75)
        if received != release.size or digest.hexdigest() != release.sha256:
            raise SetupError("Dosya boyutu veya SHA-256 uyuşmadı. Dosya kullanılmadı; indirmeyi yeniden dene.")
        _cancel(cancel)
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def safe_member(info: zipfile.ZipInfo) -> PurePosixPath:
    """Reject names unsafe on Windows even when validating on Linux."""
    raw = info.filename.replace("\\", "/")
    path = PurePosixPath(raw)
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise SetupError("ZIP güvenli olmayan bir dosya yolu içeriyor.")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in path.parts:
        if any(c in part for c in ':<>"|?*') or any(ord(c) < 32 for c in part) or part.endswith((".", " ")) or part.split(".")[0].upper() in reserved:
            raise SetupError("ZIP Windows için geçersiz bir dosya adı içeriyor.")
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
        raise SetupError("ZIP bağlantı veya özel dosya içeriyor.")
    return path


def find_launcher(root: Path) -> Path:
    root = root.resolve()
    # Look only at the extraction root and one wrapper directory, never bundled
    # dependencies or model folders. Ambiguity is resolved by explicit selection.
    candidates = []
    for directory in [root, *(p for p in root.iterdir() if p.is_dir() and not p.is_symlink())]:
        for path in directory.iterdir():
            if path.name.lower() in LAUNCHERS and path.is_file() and not path.is_symlink():
                candidates.append(path)
    if not candidates:
        raise SetupError("start_http.bat veya vcclient.exe bulunamadı. Resmî paketi çıkarıp başlatıcı dosyasını seç.")
    # Prefer documented bat over exe when both belong to the same installation.
    parents = {p.parent for p in candidates}
    if len(parents) != 1:
        raise SetupError("Birden fazla kurulum bulundu; başlatıcı dosyasını doğrudan seç.")
    return sorted(candidates, key=lambda p: LAUNCHERS.index(p.name.lower()))[0]


def extract_archive(archive: Path, destination: Path, progress: Callable[[str, float], None], cancel: threading.Event | None = None) -> None:
    """Validate the whole ZIP before extraction; only write to a fresh staging dir."""
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        total = sum(member.file_size for member in members)
        if total > MAX_EXPANDED or len(members) > 150_000:
            raise SetupError("ZIP açıldığında izin verilen boyutu aşıyor.")
        seen = set()
        paths = []
        for info in members:
            path = safe_member(info)
            folded = str(path).casefold()
            if folded in seen:
                raise SetupError("ZIP yinelenen dosya yolları içeriyor.")
            seen.add(folded)
            paths.append(path)
        if shutil.disk_usage(destination.parent).free < total + 512 * 1024**2:
            raise SetupError("ZIP'i açmak için yeterli boş disk alanı yok.")
        destination.mkdir(exist_ok=False)
        done = 0
        for info, relative in zip(members, paths):
            _cancel(cancel)
            target = destination.joinpath(*relative.parts)
            if info.is_dir() or info.filename.endswith("\\"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("xb") as output:
                while block := source.read(1024 * 1024):
                    _cancel(cancel)
                    output.write(block)
                    done += len(block)
            progress("Dosyalar açılıyor…", 75 + 24 * done / max(total, 1))


def install(release: Release, home: Path, progress: Callable[[str, float], None], cancel: threading.Event | None = None) -> Path:
    home.mkdir(parents=True, exist_ok=True)
    required = release.size * 3 + 1024**3
    if shutil.disk_usage(home).free < required:
        raise SetupError(f"Kurulum için en az {required / 1024**3:.1f} GB boş alan ayır.")
    engines = home / "engines"
    engines.mkdir(exist_ok=True)
    final = engines / release.sha256[:16]
    if final.exists():
        return find_launcher(final)
    with tempfile.TemporaryDirectory(prefix="install-", dir=home) as work:
        work = Path(work)
        archive = work / "engine.zip"
        download(release, archive, progress, cancel)
        staging = work / "unpacked"
        extract_archive(archive, staging, progress, cancel)
        launcher = find_launcher(staging)
        relative = launcher.relative_to(staging)
        (staging / "voicebridge-install.json").write_text(json.dumps(asdict(release), indent=2), encoding="utf-8")
        _cancel(cancel)
        staging.rename(final)
    progress("Motor kuruldu. Başlat düğmesiyle açabilirsin.", 100)
    return final / relative


def launch(path: Path) -> subprocess.Popen:
    if os.name != "nt":
        raise SetupError("Ses motoru Windows 11 bilgisayarında çalıştırılmalı.")
    path = path.resolve(strict=True)
    if path.name.lower() not in LAUNCHERS:
        raise SetupError("Yalnızca start_http.bat veya vcclient.exe seçilebilir.")
    if path.suffix.lower() == ".bat":
        # cmd parses batch paths itself. Reject metacharacters rather than pass
        # a user-controlled string through a shell quoting approximation.
        if any(char in str(path) for char in '%!^&|<>()\r\n"'):
            raise SetupError("Motoru C:\\VoiceBridge gibi özel işaret içermeyen bir klasöre taşı.")
        command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "call", str(path)]
    else:
        command = [str(path)]
    return subprocess.Popen(command, cwd=path.parent, creationflags=subprocess.CREATE_NEW_CONSOLE)


def gpu_report() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.stdout.strip() or "NVIDIA araç çıktısı boş. NVIDIA sürücüsünü kontrol et."
    except (OSError, subprocess.SubprocessError):
        return "NVIDIA bilgisi okunamadı. Windows'ta NVIDIA sürücüsünü kontrol et; bu sonuç tek başına GPU'nun bulunmadığını göstermez."
