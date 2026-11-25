"""Nettoyage des metadonnees des documents et images (Bouclier v2.5).

Formats geres : images (JPEG, PNG, WEBP, TIFF), PDF, Word/Excel/PowerPoint (OOXML).
100% local. Le fichier d'origine n'est jamais modifie : on renvoie de nouveaux octets.
"""
from __future__ import annotations

import io
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None
    PdfWriter = None

from . import image_meta

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}
OOXML_EXTS = {".docx", ".xlsx", ".pptx"}
SUPPORTED_EXTS = IMAGE_EXTS | OOXML_EXTS | {".pdf"}


class CleanError(Exception):
    pass


def _clean_image(data: bytes, ext: str):
    if Image is None:
        raise CleanError("Pillow est requis (pip install Pillow).")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as e:
        raise CleanError(f"Image illisible : {e}")
    found = []
    try:
        exif = img.getexif()
        if exif:
            found.append(f"EXIF ({len(exif)} champs)")
            if 0x8825 in exif:
                found.append("Coordonnees GPS")
    except Exception:
        pass
    for k in img.info:
        if k in ("icc_profile", "dpi", "transparency", "gamma", "duration", "loop"):
            continue
        if k in ("exif", "xmp", "XML:com.adobe.xmp", "comment", "photoshop") or isinstance(img.info[k], (str, bytes)):
            label = f"Metadonnee '{k}'"
            if label not in found:
                found.append(label)

    is_jpeg = ext in (".jpg", ".jpeg")
    # Plusieurs pages (TIFF) ou images animées (PNG, WebP) : tout doit être conservé.
    # (Un JPEG « multi-image » ne contient en plus que des aperçus : on les abandonne.)
    if not is_jpeg and getattr(img, "n_frames", 1) > 1:
        try:
            return image_meta.strip(data), found
        except Exception as e:
            raise CleanError(f"Image à plusieurs pages impossible à nettoyer sans en perdre : {e}")

    img = ImageOps.exif_transpose(img)
    if is_jpeg:
        img = img.convert("RGB")
    elif img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGBA" if "transparency" in img.info or img.mode in ("LA", "PA") else "RGB")

    clean = Image.new(img.mode, img.size)
    clean.paste(img)
    out = io.BytesIO()
    if is_jpeg:
        clean.save(out, format="JPEG", quality=95, subsampling=0)
    elif ext == ".webp":
        clean.save(out, format="WEBP", quality=95)
    elif ext in (".tif", ".tiff"):
        clean.save(out, format="TIFF")
    else:
        clean.save(out, format="PNG", optimize=True)
    return out.getvalue(), found


def _clean_pdf(data: bytes):
    if PdfReader is None:
        raise CleanError("pypdf est requis (pip install pypdf).")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise CleanError("PDF chiffre : deverrouillez-le d'abord.")
        found = []
        meta = reader.metadata
        if meta:
            found.extend(f"PDF {str(k).lstrip('/')}" for k, v in meta.items() if v)
        try:
            if reader.xmp_metadata is not None:
                found.append("Metadonnees XMP")
        except Exception:
            pass
        writer = PdfWriter()
        for page in reader.pages:
            # Les annotations peuvent contenir des commentaires, des liens ou des données
            # personnelles. Elles sont retirées de la copie nettoyée.
            annots = page.get("/Annots")
            if annots:
                found.append(f"Annotations PDF ({len(annots)} élément(s))")
                page.pop("/Annots", None)
            writer.add_page(page)
        # Ne pas recopier les pièces jointes embarquées ni les noms associés.
        try:
            root_obj = writer._root_object
            names = root_obj.get("/Names")
            if names and "/EmbeddedFiles" in names:
                del names["/EmbeddedFiles"]
                found.append("Pièces jointes intégrées supprimées")
        except Exception:
            pass
        writer.add_metadata({"/Producer": "", "/Creator": "", "/Author": "", "/Title": "", "/Subject": "", "/Keywords": ""})
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue(), found
    except CleanError:
        raise
    except Exception as e:
        raise CleanError(f"PDF illisible : {e}")


def _clean_ooxml(data: bytes):
    from . import office_cleaner
    return office_cleaner.clean_ooxml(data)


def clean_file(filename: str, data: bytes) -> dict:
    ext = Path(filename).suffix.lower()
    warnings = []
    if ext in IMAGE_EXTS:
        new, found = _clean_image(data, ext)
    elif ext == ".pdf":
        new, found = _clean_pdf(data)
    elif ext in OOXML_EXTS:
        new, found, warnings = _clean_ooxml(data)
    else:
        raise CleanError(f"Format non pris en charge : {ext or 'inconnu'}")
    return {
        "filename": f"{Path(filename).stem}_propre{ext}",
        "data": new,
        "found": found,
        "warnings": warnings,   # ce qui n'a PAS pu être nettoyé
        "size_before": len(data),
        "size_after": len(new),
    }
