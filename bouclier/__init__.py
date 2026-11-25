"""Package Bouclier v2.5 - Anonymiseur Universel de Documents, Textes et Images.

100% Hors-Ligne & Local sur votre PC :
- ocr_engine : Reconnaissance optique et caviardage de JPEG/PNG/Scans
- ner_engine : Reconnaissance d'entités nommées et adaptation dynamique
- redact : Détection et masquage (Noms, Adresses, Emails, Cartes, IBAN, NIR)
- image_redactor : Caviardage destructif et purge EXIF/GPS
- cleaner : Nettoyeur de métadonnées pour PDF, Word DOCX, Excel XLSX, PPTX
- scam : Analyseur local de phishing et arnaques
"""
__version__ = "3.1.0"
__author__ = "Polaether"
__url__ = "https://polaether.polaether.workers.dev/"

from . import cleaner, image_redactor, ner_engine, ocr_engine, redact, scam

# NB : `gui` n'est volontairement PAS importe ici (import paresseux) : une erreur
# dans l'interface ne doit pas empecher les autres modules de se charger.

__all__ = [
    "cleaner",
    "image_redactor",
    "ner_engine",
    "ocr_engine",
    "redact",
    "scam",
    "__version__",
]
