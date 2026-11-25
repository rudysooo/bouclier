"""Fonctions « métier de l'interface » : pur Python, sans Qt, donc testables hors écran.

Ce module ne contient AUCUNE logique de détection nouvelle : il enchaîne les appels au moteur
existant (ocr_engine, redact, cleaner, scam, ner_engine) et adapte leurs résultats à l'interface.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

APP_DIR = Path(__file__).resolve().parent.parent.parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

# Messages « le texte n'a pas été lu » (traduits par l'interface, voir ui/backends.py).
OCR_UNREAD_MISSING = ("Texte NON lu : l'OCR (Tesseract) n'est pas installé. Les données écrites sur l'image "
                      "n'ont pas été recherchées.")
OCR_FAILED_PREFIX = "Texte NON lu : l'OCR a échoué. Cause : "


# ---------------------------------------------------------------- journal d'erreurs
def log_error(text: str) -> str:
    """Écrit dans bouclier_erreur.log (dossier de l'appli, sinon dossier temporaire)."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for folder in (APP_DIR, Path(tempfile.gettempdir())):
        try:
            path = folder / "bouclier_erreur.log"
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"[{stamp}] {text}\n")
            return str(path)
        except Exception:
            continue
    return ""


def known_errors() -> tuple:
    """Exceptions du moteur dont le message est déjà lisible (affiché tel quel)."""
    from .. import cleaner, ocr_engine
    return (ocr_engine.OCRError, cleaner.CleanError)


def format_exception(exc: BaseException) -> Tuple[str, bool]:
    """(message pour l'utilisateur, faut-il journaliser la trace ?)"""
    try:
        if isinstance(exc, known_errors()):
            return str(exc), False
    except Exception:
        pass
    return f"Erreur inattendue : {type(exc).__name__}: {exc}", True


# ---------------------------------------------------------------- réglages
def settings_path() -> Path:
    from ..tesseract_setup import app_data_dir
    d = app_data_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        d = Path(tempfile.gettempdir())
    return d / "bouclier_ui.json"


def load_settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(data: dict) -> bool:
    try:
        settings_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def to_local_path(value: str) -> str:
    """Accepte un chemin ou une URL file:// (Qt) et renvoie un chemin local."""
    if value.startswith("file:"):
        from urllib.parse import unquote, urlparse
        p = urlparse(value)
        path = unquote(p.path)
        if os.name == "nt" and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        if p.netloc and os.name == "nt":  # \\serveur\partage
            path = "//" + p.netloc + path
        return path
    return value


# ---------------------------------------------------------------- images
def page_count(img) -> int:
    """Nombre de pages / d'images du fichier. Les aperçus joints aux JPEG de téléphone ne comptent pas."""
    if img.format in ("JPEG", "MPO"):
        return 1
    return int(getattr(img, "n_frames", 1))


def load_image(path: str, preview_dir: str) -> Dict:
    """Lit l'image, applique la rotation EXIF et écrit un aperçu PNG pour l'interface."""
    from PIL import Image, ImageOps
    p = Path(path)
    if p.suffix.lower() not in IMAGE_EXTS:
        raise ValueError(f"Format d'image non pris en charge : {p.suffix or 'inconnu'}")
    data = p.read_bytes()
    try:
        img = Image.open(io.BytesIO(data))
        pages = page_count(img)
        img.load()
    except Exception as e:
        raise ValueError(f"Image illisible : {e}")
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    preview = Path(preview_dir) / f"src_{uuid.uuid4().hex[:8]}.png"
    img.save(preview, format="PNG", compress_level=1)
    return {"data": data, "width": img.width, "height": img.height, "pages": pages,
            "preview": str(preview), "format": "JPEG" if data.startswith(b"\xff\xd8") else "PNG"}


def write_preview(data: bytes, preview_dir: str) -> str:
    """Écrit le résultat dans un fichier d'aperçu (PNG ou JPEG selon les octets)."""
    ext = ".jpg" if data.startswith(b"\xff\xd8") else ".png"
    path = Path(preview_dir) / f"res_{uuid.uuid4().hex[:8]}{ext}"
    path.write_bytes(data)
    return str(path)


def ocr_available() -> bool:
    from .. import ocr_engine
    return ocr_engine.has_tesseract()


def entities_from_words(words: Sequence, size: Tuple[int, int], kinds: Optional[Set[str]] = None) -> List[Dict]:
    """Associe les entités sensibles aux mots lus par l'OCR → rectangles en pixels image.

    Reprend le même rapprochement mot ↔ texte que ocr_engine.detect_and_redact_image
    (un rectangle par ligne de texte, marges 3 px / 2 px).
    """
    from .. import redact
    w, h = size
    parts: List[str] = []
    token_map = []
    pos = 0
    for b in words:
        parts.append(b.text)
        token_map.append((pos, pos + len(b.text), b))
        pos += len(b.text) + 1
    text = " ".join(parts)
    out: List[Dict] = []
    for ent in redact.find_sensitive(text, enabled_types=kinds):
        matching = [b for (s, e, b) in token_map if not (e <= ent["start"] or s >= ent["end"])]
        if not matching:
            continue
        by_line: Dict = {}
        for b in matching:
            by_line.setdefault(b.line_key, []).append(b)
        rects = []
        for line in by_line.values():
            rects.append([max(0, min(b.left for b in line) - 3), max(0, min(b.top for b in line) - 2),
                          min(w, max(b.right for b in line) + 3), min(h, max(b.bottom for b in line) + 2)])
        out.append({"id": len(out), "type": ent.get("type", "custom"), "label": ent.get("label", "Donnée sensible"),
                    "value": ent.get("value", ""), "boxes": rects, "excluded": False})
    return out


def face_detector_status() -> str:
    """État réel du détecteur, utilisable par la page Paramètres."""
    try:
        import cv2
        required = ("CascadeClassifier", "cvtColor", "resize", "COLOR_RGB2GRAY", "INTER_CUBIC")
        missing = [name for name in required if not hasattr(cv2, name)]
        if missing:
            return "OpenCV incompatible (version 5.x ou installation incorrecte) : " + ", ".join(missing) + ". Fermez Bouclier puis relancez Installer.bat pour installer OpenCV 4.x."
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        if not cascade_path.is_file():
            return "OpenCV installé, fichier du détecteur absent"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            return "OpenCV installé, détecteur facial illisible"
        return "Détection des visages prête (OpenCV Haar)"
    except Exception as exc:
        return f"Détection des visages indisponible : {type(exc).__name__}: {exc}"


def detect_face_entities(img) -> List[Dict]:
    """Détecte les visages avec OpenCV Haar et renvoie une boîte serrée par visage.

    Une installation de cv2 incomplète (par exemple un autre module cv2 installé à sa place)
    est traitée comme une indisponibilité explicite, pas comme une détection réussie à zéro visage.
    """
    try:
        import cv2
        import numpy as np
        status = face_detector_status()
        if not status.startswith("Détection des visages prête"):
            log_error("Détection des visages indisponible : " + status)
            return []
        rgb = img.convert("RGB")
        gray = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2GRAY)
        h, w = gray.shape[:2]
        # Agrandit les petites photos pour améliorer les visages éloignés, sans gonfler
        # artificiellement les coordonnées qui seront appliquées à l'image originale.
        scale = min(3.0, max(1.0, 1600.0 / max(w, h)))
        if scale > 1.0:
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        found = cascade.detectMultiScale(
            gray, scaleFactor=1.07, minNeighbors=4,
            minSize=(max(20, int(24 * scale)), max(20, int(24 * scale))),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )
        boxes = []
        for x, y, fw, fh in found:
            # Convertit la boîte détectée à l'échelle de l'image d'origine et ajoute
            # une marge légère. Le rectangle reste centré sur le visage, pas sur le corps.
            x0, y0 = int(x / scale), int(y / scale)
            x1, y1 = int((x + fw) / scale), int((y + fh) / scale)
            mx, my = max(1, int((x1 - x0) * .07)), max(1, int((y1 - y0) * .08))
            box = [max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)]
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            # Supprime les doublons qui se chevauchent fortement.
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            duplicate = False
            for old in boxes:
                ox, oy = (old[0] + old[2]) / 2, (old[1] + old[3]) / 2
                if abs(cx - ox) < min(box[2] - box[0], old[2] - old[0]) * .45 and abs(cy - oy) < min(box[3] - box[1], old[3] - old[1]) * .45:
                    duplicate = True
                    break
            if not duplicate:
                boxes.append(box)
        return [{"id": -1, "type": "face", "label": "Visage", "value": "Visage détecté", "boxes": [b], "excluded": False} for b in boxes]
    except Exception:
        log_error("Détection des visages :\n" + traceback.format_exc())
        return []


def detect_entities(data: bytes) -> Dict:
    """Détecte les données textuelles via OCR et les visages via OpenCV, sans masquer.

    Renvoie {"entities": [...], "ocr_error": str}. `ocr_error` non vide signifie que le TEXTE
    N'A PAS ÉTÉ LU : une liste vide (ou ne contenant que des visages) ne prouve alors rien.
    """
    from PIL import Image, ImageOps
    from .. import ocr_engine
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    entities: List[Dict] = []
    ocr_error = ""
    if ocr_engine.has_tesseract():
        try:
            entities.extend(entities_from_words(ocr_engine.run_tesseract_ocr(img), img.size))
        except Exception as exc:
            log_error("OCR pendant la détection combinée :\n" + traceback.format_exc())
            detail = " ".join(str(exc).split())[:200] or type(exc).__name__
            ocr_error = OCR_FAILED_PREFIX + detail
    else:
        ocr_error = OCR_UNREAD_MISSING
    entities.extend(detect_face_entities(img))
    for idx, entity in enumerate(entities):
        entity["id"] = idx
    return {"entities": entities, "ocr_error": ocr_error}


def apply_redaction(data: bytes, mode: str, rects: Sequence[Sequence[int]]) -> Dict:
    """Masque les rectangles via le moteur (auto_detect=False : les zones sont déjà choisies)."""
    from .. import ocr_engine
    return ocr_engine.detect_and_redact_image(
        data, mode=mode, extra_boxes=[tuple(int(v) for v in r) for r in rects], auto_detect=False)


def save_bytes(path: str, data: bytes) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)


def suggested_name(src_path: str, fmt: str) -> str:
    p = Path(src_path)
    return str(p.with_name(f"{p.stem}_anonymise{'.jpg' if fmt == 'JPEG' else '.png'}"))


# ---------------------------------------------------------------- texte
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _html(text: str, spans: Sequence[Tuple[int, int, str]]) -> str:
    out, pos = [], 0
    for s, e, tip in spans:
        out.append(_esc(text[pos:s]).replace("\n", "<br>"))
        out.append(f'<span style="background-color:#0f6b4d;color:#ffffff;" title="{_esc(tip)}">&nbsp;{_esc(text[s:e])}&nbsp;</span>')
        pos = e
    out.append(_esc(text[pos:]).replace("\n", "<br>"))
    return "".join(out)


def analyze_text(text: str, kinds: Set[str], style: str) -> Dict:
    from .. import redact
    res = redact.redact(text, kinds=kinds, style=style)
    findings = res["findings"]
    src_spans = [(f["start"], f["end"], f["label"]) for f in findings]
    # position des remplacements dans le texte résultat
    out_spans, shift = [], 0
    for f in findings:
        s = f["start"] + shift
        e = s + len(f["replacement"])
        out_spans.append((s, e, f["label"]))
        shift += len(f["replacement"]) - (f["end"] - f["start"])
    return {
        "redacted": res["redacted"],
        "count": len(findings),
        "findings": [{"label": f["label"], "type": f["type"], "value": f["value"], "replacement": f["replacement"]}
                     for f in findings],
        "sourceHtml": _html(text, src_spans),
        "resultHtml": _html(res["redacted"], out_spans),
    }


def text_kinds() -> List[Dict]:
    from .. import redact
    return [{"key": k, "label": v, "on": True} for k, v in redact.LABELS.items()]


# ---------------------------------------------------------------- nettoyeur
def clean_path(path: str) -> Dict:
    """Nettoie un fichier et écrit la copie « _propre » à côté de l'original (jamais d'écrasement)."""
    from .. import cleaner
    p = Path(path)
    res = cleaner.clean_file(p.name, p.read_bytes())
    out = p.with_name(res["filename"])
    n = 2
    while out.exists():
        out = p.with_name(f"{Path(res['filename']).stem}_{n}{Path(res['filename']).suffix}")
        n += 1
    out.write_bytes(res["data"])
    return {"output": str(out), "found": list(res["found"]), "warnings": list(res["warnings"]),
            "before": res["size_before"], "after": res["size_after"]}


def supported_exts() -> Set[str]:
    from .. import cleaner
    return set(cleaner.SUPPORTED_EXTS)


def human_size(n: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} o"


# ---------------------------------------------------------------- motifs
def try_pattern(regex: str, sample: str) -> Dict:
    """Teste un motif sur un texte d'exemple (ne l'enregistre pas). Mêmes règles que le registre."""
    import re
    if not regex.strip():
        return {"valid": True, "error": "", "count": 0, "html": _html(sample, [])}
    try:
        rx = re.compile(regex)
    except re.error as e:
        return {"valid": False, "error": f"Motif invalide : {e}", "count": 0, "html": _html(sample, [])}
    if rx.match(""):
        return {"valid": False, "error": "Ce motif accepte le texte vide : il masquerait n'importe quoi.",
                "count": 0, "html": _html(sample, [])}
    spans = [(m.start(), m.end(), "correspondance") for m in rx.finditer(sample) if m.end() > m.start()]
    return {"valid": True, "error": "", "count": len(spans), "html": _html(sample, spans)}
