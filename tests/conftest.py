"""Isole les tests : aucun réglage ni journal de l'utilisateur n'est lu ou modifié."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="bouclier_test_")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
