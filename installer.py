"""Installateur de Bouclier (Windows, macOS, Linux).

Etapes : 1) modules Python  2) OCR Tesseract (detecte s'il est deja la, installe sinon)
         3) raccourcis (Bureau + menu), verifies un par un.
Un journal complet est ecrit dans installation_log.txt.

Usage : python installer.py [--ocr-only] [--no-ocr] [--shortcuts-only]
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
LOG_PATH = HERE / "installation_log.txt"


def _open_log():
    for path in (LOG_PATH, Path(tempfile.gettempdir()) / "bouclier_installation_log.txt"):
        try:
            return open(path, "a", encoding="utf-8"), path
        except OSError:
            continue
    return None, None


_LOG, _LOG_FILE = _open_log()


def say(msg: str = "") -> None:
    print(msg, flush=True)
    if _LOG:
        _LOG.write(f"{datetime.now():%H:%M:%S} {msg}\n")
        _LOG.flush()


def load_setup_module():
    """Charge bouclier/tesseract_setup.py directement (stdlib uniquement, sans dependre de Pillow)."""
    spec = importlib.util.spec_from_file_location("tesseract_setup", HERE / "bouclier" / "tesseract_setup.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tesseract_setup"] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------ 1) modules Python
def install_python_modules() -> bool:
    say("[1/3] Installation des modules Python (Pillow, pypdf, pytesseract, PySide6)...")
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(HERE / "requirements.txt")]
    if sys.prefix == sys.base_prefix:  # pas dans un venv
        cmd.insert(4, "--user")
    p = subprocess.run(cmd, capture_output=True, text=True)
    for line in (p.stdout + p.stderr).strip().splitlines()[-6:]:
        say("   " + line)
    ok = all(importlib.util.find_spec(m) for m in ("PIL", "pypdf", "pytesseract", "PySide6"))
    if p.returncode != 0 or not ok:
        say("   ERREUR : modules non installes (connexion internet necessaire pour cette etape).")
        return False
    say("   OK.")
    return True


# ------------------------------------------------------------------ 2) OCR
def install_ocr() -> bool:
    say("[2/3] OCR (Tesseract)...")
    setup = load_setup_module()
    res = setup.ensure_ocr(lambda m: say("   " + m.strip()))
    say("   " + res["message"])
    return bool(res["ok"])


# ------------------------------------------------------------------ 3) raccourcis
def _launcher_python() -> str:
    """pythonw.exe (sans console) sous Windows, sinon l'interpreteur courant."""
    exe = sys.executable
    if IS_WIN:
        w = Path(exe).with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return exe


def _make_icon() -> str:
    """Genere bouclier.ico avec Pillow (facultatif)."""
    try:
        from PIL import Image, ImageDraw
        size = 256
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.polygon([(128, 12), (232, 48), (224, 150), (128, 244), (32, 150), (24, 48)], fill=(16, 185, 129, 255))
        d.polygon([(128, 40), (204, 66), (198, 142), (128, 212), (58, 142), (52, 66)], fill=(9, 13, 22, 255))
        d.rectangle([108, 90, 148, 160], fill=(16, 185, 129, 255))
        d.rectangle([90, 118, 166, 138], fill=(16, 185, 129, 255))
        path = HERE / "bouclier.ico"
        img.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        return str(path)
    except Exception:
        return ""


def _shortcut_windows() -> list:
    target, script = _launcher_python(), str(HERE / "Bouclier.pyw")
    icon = _make_icon()
    created = []
    ps1 = HERE / "creer_raccourci.ps1"
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
           "-Target", target, "-ScriptPath", script, "-WorkDir", str(HERE), "-Icon", icon]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        say("   " + ((p.stdout + p.stderr).strip().replace("\n", "\n   ") or "(pas de sortie)"))
        for line in p.stdout.splitlines():
            if line.startswith("LNK:") and Path(line[4:].strip()).exists():
                created.append(line[4:].strip())
    except Exception as e:
        say(f"   PowerShell indisponible : {e}")

    if not created:  # secours : VBScript (cscript), independant de PowerShell
        say("   Essai de secours via VBScript...")
        try:
            desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
            for d in (Path(os.environ.get("OneDrive", "")) / "Desktop", desktop):
                if d.is_dir():
                    desktop = d
                    break
            lnk = desktop / "Bouclier.lnk"
            vbs = Path(tempfile.gettempdir()) / "bouclier_lnk.vbs"
            vbs.write_text(
                'Set s = CreateObject("WScript.Shell")\n'
                f'Set l = s.CreateShortcut("{lnk}")\n'
                f'l.TargetPath = "{target}"\n'
                f'l.Arguments = Chr(34) & "{script}" & Chr(34)\n'
                f'l.WorkingDirectory = "{HERE}"\n'
                + (f'l.IconLocation = "{icon}"\n' if icon else "")
                + "l.Save\n", encoding="utf-8")
            subprocess.run(["cscript", "//nologo", str(vbs)], capture_output=True, text=True, timeout=60)
            if lnk.exists():
                created.append(str(lnk))
        except Exception as e:
            say(f"   Echec VBScript : {e}")
    return created


def _shortcut_mac() -> list:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(exist_ok=True)
    f = desktop / "Bouclier.command"
    f.write_text(f'#!/bin/bash\ncd "{HERE}"\nexec "{sys.executable}" "{HERE / "Bouclier.pyw"}"\n', encoding="utf-8")
    f.chmod(0o755)
    return [str(f)] if f.exists() else []


def _shortcut_linux() -> list:
    entry = (
        "[Desktop Entry]\nType=Application\nName=Bouclier\n"
        "Comment=Anonymisation OCR de documents et images (100% local)\n"
        f'Exec="{sys.executable}" "{HERE / "Bouclier.pyw"}"\nPath={HERE}\nTerminal=false\nCategories=Utility;\n'
    )
    icon = _make_icon()
    if icon:
        entry += f"Icon={icon}\n"
    targets = [Path.home() / ".local" / "share" / "applications"]
    try:
        d = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True).stdout.strip()
        targets.append(Path(d) if d else Path.home() / "Desktop")
    except Exception:
        targets.append(Path.home() / "Desktop")
    created = []
    for folder in targets:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            f = folder / "bouclier.desktop"
            f.write_text(entry, encoding="utf-8")
            f.chmod(0o755)
            created.append(str(f))
        except OSError:
            continue
    return created


def make_shortcuts() -> bool:
    say("[3/3] Creation des raccourcis...")
    created = _shortcut_windows() if IS_WIN else _shortcut_mac() if IS_MAC else _shortcut_linux()
    if created:
        for c in created:
            say(f"   OK, raccourci cree et verifie : {c}")
        return True
    say("   ECHEC : aucun raccourci n'a pu etre cree.")
    say(f"   Vous pouvez quand meme lancer l'application en double-cliquant sur : {HERE / 'Bouclier.pyw'}")
    return False


def main(argv) -> int:
    say("=" * 66)
    say(f"Installation de Bouclier - {datetime.now():%Y-%m-%d %H:%M}")
    say(f"Python : {sys.version.split()[0]} ({sys.executable})")
    say("=" * 66)
    if sys.version_info < (3, 9):
        say("ERREUR : Python 3.9 ou plus recent est requis (PySide6).")
        return 1
    only = "--ocr-only" in argv
    results = {}
    if not only and "--shortcuts-only" not in argv:
        results["modules"] = install_python_modules()
        if not results["modules"]:
            return 1
    if "--no-ocr" not in argv and "--shortcuts-only" not in argv:
        results["ocr"] = install_ocr()
    if not only:
        results["raccourcis"] = make_shortcuts()

    say("")
    say("RESUME : " + " | ".join(f"{k} {'OK' if v else 'A VERIFIER'}" for k, v in results.items()))
    if not results.get("ocr", True):
        say("L'OCR n'est pas pret : l'application fonctionnera en mode de secours. Relancez Installer.bat avec internet, "
            "ou utilisez le bouton 'Installer l'OCR automatiquement' dans l'application.")
    say(f"Journal complet : {_LOG_FILE}")
    return 0 if all(results.values()) else 2


if __name__ == "__main__":
    try:
        code = main(sys.argv[1:])
    except Exception:
        import traceback
        say("ERREUR INATTENDUE :\n" + traceback.format_exc())
        code = 1
    sys.exit(code)
