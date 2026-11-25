"""Lanceur Windows officiel sans console pour Bouclier (interface Qt ; --legacy = ancienne interface Tkinter).

Double-cliquer sur ce fichier (ou sur le raccourci du Bureau) pour lancer l'application.
100% Hors-Ligne & Local.

En cas de probleme, une fenetre d'erreur s'affiche et le detail est ecrit dans
bouclier_erreur.log (dossier de l'application, ou dossier temporaire a defaut).
"""
import os
import sys
import tempfile
import traceback

current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)  # utile si lance depuis un raccourci mal configure
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)


def _write_log(text):
    for folder in (current_dir, tempfile.gettempdir()):
        try:
            path = os.path.join(folder, "bouclier_erreur.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
            return path
        except Exception:
            continue
    return ""


def _show_error(message):
    """Affiche une fenetre d'erreur meme sans console (pythonw)."""
    try:
        import tkinter
        from tkinter import messagebox
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("Bouclier - impossible de demarrer", message)
        root.destroy()
        return
    except Exception:
        pass
    if sys.platform.startswith("win"):  # Tkinter lui-meme absent : boite native Windows
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, "Bouclier - impossible de demarrer", 0x10)
        except Exception:
            pass


if sys.version_info < (3, 9):
    _show_error("Bouclier necessite Python 3.9 ou plus recent.\nVersion detectee : " + sys.version.split()[0])
    sys.exit(1)

try:
    if "--legacy" in sys.argv:  # ancienne interface Tkinter, conservee en secours
        sys.argv.remove("--legacy")
        from bouclier.gui import main
    else:
        from bouclier.ui.main import main
    code = main()
    sys.exit(code or 0)
except SystemExit:
    raise
except Exception as e:
    details = traceback.format_exc()
    path = _write_log(details)
    hint = ""
    if isinstance(e, ModuleNotFoundError) or "tkinter" in str(e).lower() or "PySide6" in str(e):
        hint = "\n\nUn module manque (PySide6, Pillow...) : relancez Installer.bat. Secours : Bouclier.pyw --legacy"
    _show_error("Bouclier n'a pas pu demarrer :\n\n%s: %s%s\n\nDetails : %s" % (type(e).__name__, e, hint, path))
    sys.exit(1)
