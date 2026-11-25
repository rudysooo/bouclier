"""Detection et installation automatique de l'OCR Tesseract (Bouclier v2.5).

Module 100% bibliotheque standard (utilisable avant meme d'installer Pillow & co).
Internet n'est utilise QUE pour telecharger Tesseract / les langues, une seule fois.
Ensuite, l'application fonctionne totalement hors-ligne.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

LANGS = ("fra", "eng")
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

LANG_URLS = [
    "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata",
    "https://github.com/tesseract-ocr/tessdata/raw/main/{lang}.traineddata",
]
GITHUB_LATEST_API = "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest"
FALLBACK_INSTALLER_URL = (
    "https://github.com/UB-Mannheim/tesseract/releases/download/"
    "v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
)
WINGET_ID = "UB-Mannheim.TesseractOCR"

Log = Callable[[str], None]


def _noop(_msg: str) -> None:
    pass


# ---------------------------------------------------------------- dossiers
def app_data_dir() -> Path:
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "Bouclier"


def tessdata_dir() -> Path:
    """Dossier utilisateur (sans droits admin) ou sont stockees les langues OCR."""
    return app_data_dir() / "tessdata"


# ---------------------------------------------------------------- detection
def _windows_candidates() -> List[str]:
    paths = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "LOCALAPPDATA"):
        root = os.environ.get(var)
        if root:
            paths.append(os.path.join(root, "Tesseract-OCR", "tesseract.exe"))
            paths.append(os.path.join(root, "Programs", "Tesseract-OCR", "tesseract.exe"))
    paths.append(str(app_data_dir() / "Tesseract-OCR" / "tesseract.exe"))
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (r"SOFTWARE\Tesseract-OCR", r"SOFTWARE\WOW6432Node\Tesseract-OCR"):
                try:
                    with winreg.OpenKey(hive, sub) as key:
                        install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                        paths.append(os.path.join(install_dir, "tesseract.exe"))
                except OSError:
                    continue
    except ImportError:
        pass
    return paths


def find_tesseract() -> Optional[str]:
    """Chemin de tesseract s'il est deja installe (PATH, emplacements usuels, registre)."""
    env = os.environ.get("TESSERACT_CMD")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("tesseract")
    if found:
        return found
    candidates = _windows_candidates() if IS_WIN else [
        "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract", "/snap/bin/tesseract",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None


def _system_tessdata(cmd: Optional[str]) -> List[Path]:
    dirs = []
    if cmd:
        dirs.append(Path(cmd).resolve().parent / "tessdata")
    dirs += [Path("/usr/share/tesseract-ocr/5/tessdata"), Path("/usr/share/tesseract-ocr/4.00/tessdata"),
             Path("/usr/share/tessdata"), Path("/opt/homebrew/share/tessdata"), Path("/usr/local/share/tessdata")]
    return dirs


def available_languages(cmd: Optional[str] = None) -> Dict[str, Path]:
    """Langues effectivement disponibles : celles de Bouclier d'abord, puis celles du systeme."""
    cmd = cmd or find_tesseract()
    found: Dict[str, Path] = {}
    for d in [tessdata_dir()] + _system_tessdata(cmd):
        for lang in LANGS:
            f = d / f"{lang}.traineddata"
            if lang not in found and f.is_file() and f.stat().st_size > 50_000:
                found[lang] = f
    return found


def missing_languages(cmd: Optional[str] = None) -> List[str]:
    have = available_languages(cmd)
    return [l for l in LANGS if l not in have]


def status() -> Dict[str, object]:
    cmd = find_tesseract()
    return {"cmd": cmd, "installed": bool(cmd), "missing_langs": missing_languages(cmd) if cmd else list(LANGS)}


# ---------------------------------------------------------------- telechargement
def _download(url: str, dest: Path, log: Log, min_size: int = 50_000, timeout: int = 60) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(dest.parent), suffix=".part")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Bouclier-installer"})
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, "wb") as out:
            shutil.copyfileobj(resp, out)
        if tmp.stat().st_size < min_size:
            raise OSError("fichier telecharge trop petit")
        os.replace(tmp, dest)
        return True
    except Exception as e:
        log(f"   echec ({url}) : {e}")
        return False
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def download_languages(langs: List[str], log: Log = _noop) -> List[str]:
    """Telecharge les langues manquantes dans le dossier utilisateur. Renvoie celles qui ont echoue."""
    failed = []
    for lang in langs:
        log(f"   telechargement de la langue OCR '{lang}'...")
        dest = tessdata_dir() / f"{lang}.traineddata"
        if not any(_download(u.format(lang=lang), dest, log) for u in LANG_URLS):
            failed.append(lang)
    return failed


# ---------------------------------------------------------------- installation Tesseract
def _run(cmd: List[str], log: Log, timeout: int = 900) -> int:
    try:
        flags = subprocess.CREATE_NO_WINDOW if IS_WIN else 0
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        tail = (p.stdout or p.stderr or "").strip().splitlines()[-3:]
        for line in tail:
            log(f"   {line}")
        return p.returncode
    except FileNotFoundError:
        return 127
    except Exception as e:
        log(f"   erreur : {e}")
        return 1


def _install_windows(log: Log) -> None:
    if shutil.which("winget"):
        log("-> Installation via winget (acceptez la fenetre Windows 'Controle de compte' si elle apparait)...")
        _run(["winget", "install", "--id", WINGET_ID, "-e", "--silent",
              "--accept-package-agreements", "--accept-source-agreements"], log)
        if find_tesseract():
            return
        log("   winget n'a pas abouti, essai par telechargement direct...")
    else:
        log("-> winget indisponible, telechargement direct de l'installateur Tesseract...")

    urls = []
    try:
        req = urllib.request.Request(GITHUB_LATEST_API, headers={"User-Agent": "Bouclier-installer"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            for asset in json.load(resp).get("assets", []):
                name = asset.get("name", "")
                if name.startswith("tesseract-ocr-w64-setup") and name.endswith(".exe"):
                    urls.append(asset["browser_download_url"])
    except Exception as e:
        log(f"   (API GitHub inaccessible : {e})")
    urls.append(FALLBACK_INSTALLER_URL)

    setup = Path(tempfile.gettempdir()) / "tesseract-setup-bouclier.exe"
    if not any(_download(u, setup, log, min_size=5_000_000, timeout=300) for u in urls):
        return
    log("-> Installation silencieuse de Tesseract (fenetre 'Controle de compte' a accepter)...")
    ps = f"Start-Process -FilePath '{setup}' -ArgumentList '/S' -Verb RunAs -Wait"
    _run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], log)
    try:
        setup.unlink()
    except OSError:
        pass


def _install_mac(log: Log) -> None:
    if shutil.which("brew"):
        log("-> Installation via Homebrew...")
        _run(["brew", "install", "tesseract"], log)
    else:
        log("   Homebrew absent : installez-le (https://brew.sh) puis lancez : brew install tesseract")


def _install_linux(log: Log) -> None:
    elevate = [] if (hasattr(os, "geteuid") and os.geteuid() == 0) else (["sudo"] if shutil.which("sudo") else [])
    if shutil.which("apt-get"):
        _run(elevate + ["apt-get", "install", "-y", "tesseract-ocr", "tesseract-ocr-fra", "tesseract-ocr-eng"], log)
    elif shutil.which("dnf"):
        _run(elevate + ["dnf", "install", "-y", "tesseract", "tesseract-langpack-fra"], log)
    elif shutil.which("pacman"):
        _run(elevate + ["pacman", "-S", "--noconfirm", "tesseract", "tesseract-data-fra", "tesseract-data-eng"], log)
    else:
        log("   Gestionnaire de paquets inconnu : installez le paquet 'tesseract-ocr' manuellement.")


def ensure_ocr(log: Log = _noop) -> Dict[str, object]:
    """Detecte Tesseract (deja present = rien a faire), l'installe sinon, puis complete les langues."""
    log("Recherche de Tesseract sur cet ordinateur...")
    cmd = find_tesseract()
    if cmd:
        log(f"OK : Tesseract deja installe ({cmd}).")
    else:
        log("Tesseract est absent : installation automatique.")
        (_install_windows if IS_WIN else _install_mac if IS_MAC else _install_linux)(log)
        cmd = find_tesseract()
        if not cmd:
            log("ECHEC : Tesseract n'a pas pu etre installe automatiquement.")
            return {"ok": False, "cmd": None, "missing_langs": list(LANGS),
                    "message": "Installation de Tesseract impossible (connexion ? fenetre administrateur refusee ?)."}
        log(f"OK : Tesseract installe ({cmd}).")

    miss = missing_languages(cmd)
    if miss:
        log(f"Langues OCR manquantes : {', '.join(miss)}")
        download_languages(miss, log)
        miss = missing_languages(cmd)
    else:
        log("OK : langues francais + anglais disponibles.")
    ok = not miss
    msg = "OCR pret (francais + anglais)." if ok else f"Langues manquantes : {', '.join(miss)} (connexion internet requise)."
    return {"ok": ok, "cmd": cmd, "missing_langs": miss, "message": msg}
