#!/usr/bin/env bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Linux : Qt a besoin de quelques bibliotheques systeme (ex. Debian/Ubuntu : sudo apt install libxcb-cursor0 libegl1)

# Environnement virtuel local : evite l'erreur "externally-managed-environment" des Python recents
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python installer.py "$@"
echo
echo "Lancement : .venv/bin/python -m bouclier   (ou via le raccourci cree)"
