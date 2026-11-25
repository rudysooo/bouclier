"""Module d'Optical Character Recognition (OCR) et Caviardage d'Images (Bouclier v2.5).

100% LOCAL ET HORS-LIGNE :
- Analyse les images (JPEG, PNG, WEBP, TIFF)
- Détecte le texte et extrait les coordonnées précises des boîtes englobantes
- Identifie les entités sensibles (Noms, Adresses, E-mails, Téléphones, IBAN, Cartes...)
- Masque (caviarage noir, flou gaussien ou mosaïque) directement sur l'image
- Conserve le format d'origine (JPEG -> JPEG, PNG -> PNG)
- Purgé de toutes métadonnées EXIF / GPS.
"""
from __future__ import annotations

import io
import math
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

from . import tesseract_setup


class OCRError(Exception):
    pass


class OCRWordBox:
    def __init__(self, text: str, left: int, top: int, width: int, height: int, confidence: float = 80.0, line_key=None):
        self.text = text
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.confidence = confidence
        self.line_key = line_key

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


_TESS_STATE: Dict[str, object] = {}


def reset_detection() -> None:
    """A appeler apres une installation de Tesseract pour forcer une nouvelle detection."""
    _TESS_STATE.clear()


def _setup() -> None:
    if "ok" in _TESS_STATE:
        return
    ok, lang = False, "eng"
    cmd = tesseract_setup.find_tesseract() if pytesseract is not None else None
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        try:
            pytesseract.get_tesseract_version()
            ok = True
        except Exception:
            ok = False
    _TESS_STATE["system_prefix"] = os.environ.get("TESSDATA_PREFIX")
    if ok:
        have = tesseract_setup.available_languages(cmd)
        local_dir = tesseract_setup.tessdata_dir()
        local = [l for l in tesseract_setup.LANGS if l in have and have[l].parent == local_dir]
        if local:
            # Langues telechargees par Bouclier. On passe par la variable d'environnement
            # (et non par --tessdata-dir) : pytesseract gere mal les guillemets sous Windows.
            os.environ["TESSDATA_PREFIX"] = str(local_dir)
            lang = "+".join(local)
        else:
            try:
                installed = set(pytesseract.get_languages(config=""))
                wanted = [l for l in tesseract_setup.LANGS if l in installed]
                lang = "+".join(wanted) if wanted else (sorted(installed - {"osd"}) or ["eng"])[0]
            except Exception:
                lang = "eng"
    _TESS_STATE.update(ok=ok, lang=lang, config="", cmd=cmd)


def has_tesseract() -> bool:
    """True si Tesseract est installe et utilisable (resultat mis en cache)."""
    _setup()
    return bool(_TESS_STATE["ok"])


def ocr_selftest() -> Optional[str]:
    """Lit une petite image de test. Renvoie None si l'OCR fonctionne, sinon le message d'erreur reel."""
    if not has_tesseract():
        return "Tesseract introuvable."
    try:
        from PIL import ImageFont
        try:
            font = ImageFont.load_default(size=44)
        except TypeError:
            font = ImageFont.load_default()
        img = Image.new("RGB", (460, 110), "white")
        ImageDraw.Draw(img).text((20, 25), "Bouclier 2026", fill="black", font=font)
        words = run_tesseract_ocr(img)
        if not any(w.text for w in words):
            return "Tesseract s'execute mais ne lit aucun texte."
        return None
    except Exception as e:
        return str(e)


def ocr_status() -> Dict[str, object]:
    """Etat detaille de l'OCR pour l'interface (inclut un vrai test de lecture)."""
    _setup()
    st = tesseract_setup.status()
    st["lang"] = _TESS_STATE.get("lang")
    st["error"] = ocr_selftest() if _TESS_STATE["ok"] else "Tesseract introuvable."
    st["usable"] = st["error"] is None
    return st


def run_tesseract_ocr(img: Image.Image) -> List[OCRWordBox]:
    """Lit l'image avec Tesseract. Leve OCRError (avec la vraie cause) si Tesseract echoue."""
    if not has_tesseract():
        raise OCRError("Tesseract n'est pas installe.")
    attempts = [str(_TESS_STATE["lang"])]
    if attempts[0] != "eng":
        attempts.append("eng")
    last_err = None
    data = None
    for i, lang in enumerate(attempts):
        try:
            if i == 1:  # repli : on retire notre dossier de langues et on laisse Tesseract utiliser le sien
                prev = _TESS_STATE.get("system_prefix")
                if prev:
                    os.environ["TESSDATA_PREFIX"] = prev
                else:
                    os.environ.pop("TESSDATA_PREFIX", None)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, lang=lang)
            break
        except Exception as e:
            last_err = e
    if data is None:
        raise OCRError(f"Tesseract a echoue : {last_err}")

    boxes: List[OCRWordBox] = []
    for i in range(len(data["text"])):
        word = str(data["text"][i]).strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if word and conf > 20:
            boxes.append(OCRWordBox(
                text=word,
                left=int(data["left"][i]), top=int(data["top"][i]),
                width=int(data["width"][i]), height=int(data["height"][i]),
                confidence=conf,
                line_key=(data["block_num"][i], data["par_num"][i], data["line_num"][i]),
            ))
    return boxes


def run_heuristic_text_detection(img: Image.Image) -> List[OCRWordBox]:
    """Détecteur heuristique de lignes de texte par morphologie d'image en pur Python/Pillow."""
    w, h = img.size
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)

    line_height = max(14, min(36, h // 25))
    step = max(6, line_height // 2)

    boxes: List[OCRWordBox] = []
    y = step
    while y < h - line_height:
        band = edges.crop((0, y, w, y + line_height))
        extrema = band.getextrema()
        if extrema and extrema[1] > 140:
            boxes.append(OCRWordBox(
                text="[Texte détecté]",
                left=int(w * 0.05),
                top=y,
                width=int(w * 0.90),
                height=line_height,
                confidence=70.0
            ))
            y += line_height
        else:
            y += step

    return boxes[:15]


def detect_and_redact_image(
    source_image: Union[str, Path, bytes, Image.Image],
    output_path: Optional[Union[str, Path]] = None,
    mode: str = "blackout",
    sensitive_types: Optional[set] = None,
    custom_keywords: Optional[List[str]] = None,
    extra_boxes: Optional[List[Tuple[int, int, int, int]]] = None,
    auto_detect: bool = True,
) -> Dict:
    """Analyse une image par OCR, repère les données sensibles et les masque de façon irréversible."""
    if Image is None:
        raise OCRError("Pillow est requis (pip install Pillow).")

    from . import redact

    original_format = "PNG"
    if isinstance(source_image, (str, Path)):
        p = Path(source_image)
        if p.suffix.lower() in (".jpg", ".jpeg"):
            original_format = "JPEG"
        img = Image.open(source_image)
    elif isinstance(source_image, bytes):
        if source_image.startswith(b"\xff\xd8"):
            original_format = "JPEG"
        img = Image.open(io.BytesIO(source_image))
    else:
        img = source_image
        if getattr(img, "format", None) in ("JPEG", "JPG"):
            original_format = "JPEG"

    # Un seul plan est traité : l'appelant doit pouvoir le signaler (aperçus des JPEG exclus).
    pages = 1 if img.format in ("JPEG", "MPO") else int(getattr(img, "n_frames", 1))
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    w, h = img.size

    ocr_boxes: List[OCRWordBox] = []
    using_tesseract = False
    if auto_detect:
        if not has_tesseract():
            if not extra_boxes:
                raise OCRError(
                    "L'OCR (Tesseract) n'est pas installe : impossible de reperer les donnees automatiquement.\n"
                    "Installez-le (bouton « Installer l'OCR automatiquement ») ou tracez des zones a la souris."
                )
            auto_detect = False  # zones manuelles uniquement
        else:
            using_tesseract = True
            ocr_boxes = run_tesseract_ocr(img)  # leve OCRError avec la cause reelle en cas d'echec

    redaction_rectangles: List[Dict] = []
    entities_found: List[Dict] = []

    if using_tesseract and ocr_boxes:
        full_text_parts = []
        token_map: List[Tuple[int, int, OCRWordBox]] = []
        current_pos = 0

        for box in ocr_boxes:
            word = box.text
            start = current_pos
            end = start + len(word)
            full_text_parts.append(word)
            token_map.append((start, end, box))
            current_pos = end + 1

        full_text = " ".join(full_text_parts)
        ner_results = redact.find_sensitive(full_text, enabled_types=sensitive_types)

        if custom_keywords:
            for kw in custom_keywords:
                if not kw.strip():
                    continue
                regex = re.compile(rf"\b{re.escape(kw.strip())}\b", re.IGNORECASE)
                for m in regex.finditer(full_text):
                    ner_results.append({
                        "type": "name",
                        "label": "Mot-clé personnalisé",
                        "start": m.start(),
                        "end": m.end(),
                        "value": m.group(0),
                    })

        for entity in ner_results:
            e_start = entity["start"]
            e_end = entity["end"]
            matching_boxes = [box for (s, e, box) in token_map if not (e <= e_start or s >= e_end)]

            if matching_boxes:
                # un rectangle par ligne de texte (sinon une donnee sur 2 lignes noircit tout le bloc)
                by_line: Dict = {}
                for b in matching_boxes:
                    by_line.setdefault(b.line_key, []).append(b)
                for line_boxes in by_line.values():
                    min_x = max(0, min(b.left for b in line_boxes) - 3)
                    min_y = max(0, min(b.top for b in line_boxes) - 2)
                    max_x = min(w, max(b.right for b in line_boxes) + 3)
                    max_y = min(h, max(b.bottom for b in line_boxes) + 2)
                    redaction_rectangles.append({
                        "box": (min_x, min_y, max_x, max_y),
                        "label": f"{entity.get('label', 'Donnée sensible')} : {entity.get('value', '')}",
                        "type": entity.get("type", "custom"),
                        "mode": mode,
                    })
                entities_found.append(entity)
    else:
        for i, box in enumerate(ocr_boxes):
            redaction_rectangles.append({
                "box": (box.left, box.top, box.right, box.bottom),
                "label": f"Zone confidentielle #{i+1}",
                "type": "custom",
                "mode": mode,
            })
            entities_found.append({"type": "zone", "label": "Ligne confidentielle", "value": "texte image"})

    # Zones tracees a la main (coordonnees en pixels de l'image, apres rotation EXIF)
    for (x0, y0, x1, y1) in (extra_boxes or []):
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        redaction_rectangles.append({"box": (x0, y0, x1, y1), "label": "Zone manuelle", "type": "manual", "mode": mode})
        entities_found.append({"type": "manual", "label": "Zone manuelle", "value": f"({x0},{y0})-({x1},{y1})"})

    from . import image_redactor

    working_img = img.copy()
    for item in redaction_rectangles:
        box_tuple = item["box"]
        b_mode = item["mode"]
        if b_mode == "pixelate":
            image_redactor.pixelate_region(working_img, box_tuple, pixel_size=max(8, (box_tuple[3] - box_tuple[1]) // 2))
        elif b_mode == "blur":
            image_redactor.blur_region(working_img, box_tuple, radius=max(10, (box_tuple[3] - box_tuple[1]) // 2))
        else:
            image_redactor.blackout_region(working_img, box_tuple, label="CAVIARDÉ")

    out_buf = io.BytesIO()
    clean_canvas = Image.new("RGB" if original_format == "JPEG" else working_img.mode, working_img.size)
    clean_canvas.paste(working_img)

    if original_format == "JPEG":
        clean_canvas.save(out_buf, format="JPEG", quality=95, subsampling=0)
    else:
        clean_canvas.save(out_buf, format="PNG", optimize=True)

    result_bytes = out_buf.getvalue()

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_bytes(result_bytes)

    return {
        "format": original_format,
        "pages": pages,
        "width": w,
        "height": h,
        "ocr_engine": "tesseract" if using_tesseract else "manual",
        "entities_count": len(entities_found),
        "entities": entities_found,
        "redacted_rectangles": len(redaction_rectangles),
        "data": result_bytes,
        "output_path": str(output_path) if output_path else None,
    }
