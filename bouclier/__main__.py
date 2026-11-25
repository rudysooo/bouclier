"""Permet de lancer l'application avec : python -m bouclier   (ajouter --legacy pour l'ancienne interface)"""
import sys

if "--legacy" in sys.argv:
    sys.argv.remove("--legacy")
    from .gui import main
else:
    from .ui.main import main

if __name__ == "__main__":
    sys.exit(main() or 0)
