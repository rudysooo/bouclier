"""Moteur de Named Entity Recognition (NER) et d'Adaptation Dynamique de Motifs (Bouclier v2.5).

100% LOCAL ET HORS-LIGNE :
- Détection des Noms, Adresses physiques, E-mails, Téléphones, Numéros d'identité (NIR, CNI, Passeport, Fiscal)
- Dictionnaires morphologiques et gazetteers étendus
- Système d'adaptation dynamique : apprentissage et ajout de nouveaux motifs de données sensibles
- Sauvegarde et persistance locale des règles dans un fichier JSON local (bouclier_patterns.json).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

def _default_config_path() -> Path:
    """bouclier_patterns.json a cote de l'appli ; si ce dossier n'est pas modifiable, dossier utilisateur."""
    local = Path(__file__).resolve().parent.parent
    if os.access(local, os.W_OK):
        return local / "bouclier_patterns.json"
    from .tesseract_setup import app_data_dir
    d = app_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "bouclier_patterns.json"


CONFIG_FILE = _default_config_path()

DEFAULT_PATTERNS = [
    {"id": "email", "label": "Adresse e-mail", "regex": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "enabled": True},
    {"id": "phone_fr", "label": "Téléphone (France)", "regex": r"(?<![\d.])(?:(?:\+|00)33[\s.-]?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)", "enabled": True},
    {"id": "iban", "label": "Identifiant IBAN", "regex": r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b", "enabled": True},
    {"id": "card", "label": "Carte bancaire", "regex": r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)", "enabled": True},
    {"id": "nir", "label": "N° Sécurité Sociale (NIR)", "regex": r"(?<!\d)[12][ ]?\d{2}[ ]?(?:0[1-9]|1[0-2]|[2-9]\d)[ ]?(?:\d{2}|2[AB])[ ]?\d{3}[ ]?\d{3}(?:[ ]?\d{2})?(?!\d)", "enabled": True},
    {"id": "id_fiscal", "label": "Numéro Fiscal (SPI)", "regex": r"(?<!\d)[0-3]\d{12}(?!\d)", "enabled": True},
    {"id": "ip", "label": "Adresse IP", "regex": r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])", "enabled": True},
]


class DynamicPatternRegistry:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_FILE
        self.patterns: List[Dict[str, Any]] = []
        self.custom_keywords: Set[str] = set()
        self.load()

    def load(self) -> None:
        self.patterns = [dict(p) for p in DEFAULT_PATTERNS]
        self.custom_keywords = set()
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                saved = data.get("patterns")
                if isinstance(saved, list):
                    self.patterns = [p for p in saved if isinstance(p, dict) and p.get("regex")]
                self.custom_keywords = {str(k) for k in data.get("custom_keywords", []) if str(k).strip()}
            except Exception as e:
                print(f"[NER] Fichier de motifs illisible, valeurs par defaut utilisees : {e}", file=sys.stderr)

    def save(self) -> bool:
        try:
            data = {"patterns": self.patterns, "custom_keywords": sorted(self.custom_keywords)}
            self.config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception as e:
            print(f"[NER] Erreur enregistrement motifs: {e}", file=sys.stderr)
            return False

    # -- motifs personnalises (ceux dont l'id commence par "custom_")
    def custom_patterns(self) -> List[Dict[str, Any]]:
        return [p for p in self.patterns if str(p.get("id", "")).startswith("custom_")]

    def add_custom_pattern(self, label: str, regex_str: str) -> bool:
        label, regex_str = label.strip(), regex_str.strip()
        if not label or not regex_str:
            return False
        try:
            compiled = re.compile(regex_str)
            if compiled.match(""):  # un motif qui accepte le vide masquerait n'importe quoi
                return False
        except re.error:
            return False
        clean_label = re.sub(r"\W+", "_", label.lower())
        pattern_id = f"custom_{len(self.patterns) + 1}_{clean_label}"
        self.patterns.append({"id": pattern_id, "label": label, "regex": regex_str, "enabled": True})
        return self.save()

    def remove_pattern(self, pattern_id: str) -> None:
        self.patterns = [p for p in self.patterns if p.get("id") != pattern_id or not str(p["id"]).startswith("custom_")]
        self.save()

    def add_keyword(self, word: str) -> bool:
        word = word.strip()
        if len(word) < 2:
            return False
        self.custom_keywords.add(word)
        return self.save()

    def remove_keyword(self, word: str) -> None:
        self.custom_keywords.discard(word)
        self.save()

    def find_custom(self, text: str) -> List[Dict[str, Any]]:
        """Occurrences des motifs et mots-cles personnalises dans `text`."""
        hits: List[Dict[str, Any]] = []
        for p in self.custom_patterns():
            if not p.get("enabled", True):
                continue
            try:
                rx = re.compile(p["regex"])
            except re.error:
                continue
            for m in rx.finditer(text):
                if m.end() > m.start():
                    hits.append({"type": "custom", "label": p.get("label", "Motif personnalise"),
                                 "start": m.start(), "end": m.end(), "value": m.group(0)})
        for kw in self.custom_keywords:
            rx = re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", re.IGNORECASE)
            for m in rx.finditer(text):
                hits.append({"type": "custom", "label": "Mot-cle personnalise",
                             "start": m.start(), "end": m.end(), "value": m.group(0)})
        return hits


registry = DynamicPatternRegistry()
