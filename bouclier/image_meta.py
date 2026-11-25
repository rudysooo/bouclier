"""Retrait SANS RECOMPRESSION des métadonnées d'images JPEG, PNG et WebP (100 % local).

On recopie uniquement les blocs nécessaires à l'affichage : EXIF (dont GPS), XMP, IPTC,
commentaires, dates, miniatures et données ajoutées après la fin de l'image disparaissent.
Les pixels, la qualité et les animations ne changent pas. Seule l'orientation est conservée
(sinon la photo s'afficherait couchée).
"""
from __future__ import annotations

import io
import struct
import zlib
from typing import Optional

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Blocs PNG utiles à l'affichage (y compris l'animation APNG). Tout autre bloc « auxiliaire » part.
_PNG_KEEP = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"cHRM", b"gAMA", b"iCCP", b"sBIT", b"sRGB",
             b"cICP", b"bKGD", b"hIST", b"pHYs", b"sPLT", b"acTL", b"fcTL", b"fdAT"}
_WEBP_KEEP = {b"VP8 ", b"VP8L", b"VP8X", b"ALPH", b"ANIM", b"ANMF", b"ICCP"}


def kind_of(data: bytes) -> Optional[str]:
    """« jpeg », « png », « webp », « tiff » ou None, d'après les premiers octets."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(PNG_SIGNATURE):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    return None


def _orientation(data: bytes) -> int:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            value = int(img.getexif().get(0x0112, 1))
        return value if 2 <= value <= 8 else 1
    except Exception:
        return 1


def _orientation_tiff(value: int) -> bytes:
    """Bloc EXIF minimal contenant uniquement l'orientation."""
    return (b"MM\x00*\x00\x00\x00\x08" + b"\x00\x01" + b"\x01\x12\x00\x03\x00\x00\x00\x01"
            + struct.pack(">HH", value, 0) + b"\x00\x00\x00\x00")


def strip_jpeg(data: bytes) -> bytes:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("JPEG invalide")
    out = bytearray(b"\xff\xd8")
    orientation = _orientation(data)
    inserted = orientation == 1
    i, n = 2, len(data)
    while i < n:
        if data[i] != 0xFF:
            raise ValueError("JPEG invalide : marqueur attendu")
        while i < n and data[i] == 0xFF:  # octets de remplissage
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        if marker == 0xD9:  # fin d'image : tout ce qui suit (2e image, vidéo…) est abandonné
            out += b"\xff\xd9"
            return bytes(out)
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            out += bytes((0xFF, marker))
            continue
        if i + 2 > n:
            break
        length = int.from_bytes(data[i:i + 2], "big")
        if length < 2 or i + length > n:
            raise ValueError("JPEG invalide : segment tronqué")
        segment = data[i:i + length]
        i += length
        keep = True
        if 0xE0 <= marker <= 0xEF:  # APPn : seuls JFIF, le profil couleur et Adobe servent à l'affichage
            keep = (marker == 0xE0 and segment[2:7] == b"JFIF\x00") or marker == 0xEE \
                or (marker == 0xE2 and segment[2:14] == b"ICC_PROFILE\x00")
        elif marker == 0xFE:  # commentaire
            keep = False
        if not inserted and marker != 0xE0:
            payload = b"Exif\x00\x00" + _orientation_tiff(orientation)
            out += b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
            inserted = True
        if keep:
            out += bytes((0xFF, marker)) + segment
        if marker == 0xDA:  # données compressées : jusqu'au prochain vrai marqueur
            j = i
            while True:
                j = data.find(b"\xff", j)
                if j < 0 or j + 1 >= n:
                    out += data[i:]  # fichier sans marqueur de fin : on garde l'image telle quelle
                    return bytes(out)
                nxt = data[j + 1]
                if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:
                    j += 2
                elif nxt == 0xFF:
                    j += 1
                else:
                    break
            out += data[i:j]
            i = j
    raise ValueError("JPEG invalide : fin inattendue")


def _png_chunk(kind: bytes, body: bytes) -> bytes:
    return len(body).to_bytes(4, "big") + kind + body + (zlib.crc32(kind + body) & 0xFFFFFFFF).to_bytes(4, "big")


def strip_png(data: bytes) -> bytes:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("PNG invalide")
    out = bytearray(PNG_SIGNATURE)
    orientation = _orientation(data)
    i, n = len(PNG_SIGNATURE), len(data)
    while i + 12 <= n:
        length = int.from_bytes(data[i:i + 4], "big")
        kind = data[i + 4:i + 8]
        end = i + 12 + length
        if end > n:
            raise ValueError("PNG invalide : bloc tronqué")
        # bloc « critique » (majuscule initiale) : indispensable au décodage
        if kind in _PNG_KEEP or not kind[:1].islower():
            out += data[i:end]
        if kind == b"IHDR" and orientation != 1:
            out += _png_chunk(b"eXIf", _orientation_tiff(orientation))
        if kind == b"IEND":
            return bytes(out)
        i = end
    raise ValueError("PNG invalide : fin inattendue")


def strip_webp(data: bytes) -> bytes:
    if kind_of(data) != "webp":
        raise ValueError("WebP invalide")
    orientation = _orientation(data)
    chunks = []
    i, n = 12, min(len(data), 8 + int.from_bytes(data[4:8], "little"))
    while i + 8 <= n:
        kind = data[i:i + 4]
        length = int.from_bytes(data[i + 4:i + 8], "little")
        if i + 8 + length > n:
            raise ValueError("WebP invalide : bloc tronqué")
        if kind in _WEBP_KEEP:
            chunks.append([kind, bytearray(data[i + 8:i + 8 + length])])
        i += 8 + length + (length & 1)
    if not chunks:
        raise ValueError("WebP invalide : aucune image")
    extended = chunks[0][0] == b"VP8X"
    if extended:
        flags = chunks[0][1][0] & ~0x0C  # drapeaux EXIF (0x08) et XMP (0x04)
        if orientation != 1:
            flags |= 0x08
            chunks.append([b"EXIF", bytearray(_orientation_tiff(orientation))])
        chunks[0][1][0] = flags
    body = bytearray(b"WEBP")
    for kind, content in chunks:
        body += kind + len(content).to_bytes(4, "little") + content + (b"\x00" if len(content) & 1 else b"")
    return b"RIFF" + len(body).to_bytes(4, "little") + bytes(body)


def clean_tiff(data: bytes) -> bytes:
    """Réécrit toutes les pages d'un TIFF sans aucune métadonnée (compression sans perte)."""
    from PIL import Image, ImageOps, ImageSequence
    pages = []
    with Image.open(io.BytesIO(data)) as img:
        for frame in ImageSequence.Iterator(img):
            frame.load()
            page = ImageOps.exif_transpose(frame.copy())
            if page.mode not in ("1", "L", "LA", "RGB", "RGBA", "CMYK", "I;16"):
                page = page.convert("RGBA" if page.mode in ("PA",) or "transparency" in page.info else "RGB")
            clean = Image.new(page.mode, page.size)
            clean.paste(page)
            pages.append(clean)
    out = io.BytesIO()
    options = {"format": "TIFF"}
    if len(pages) > 1:
        options.update(save_all=True, append_images=pages[1:], compression="tiff_deflate")
    pages[0].save(out, **options)
    return out.getvalue()


def has_gps(data: bytes) -> bool:
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            return 0x8825 in img.getexif()
    except Exception:
        return False


def strip(data: bytes) -> bytes:
    """Nettoie une image JPEG, PNG, WebP ou TIFF ; lève ValueError pour tout autre contenu."""
    kind = kind_of(data)
    if kind == "jpeg":
        return strip_jpeg(data)
    if kind == "png":
        return strip_png(data)
    if kind == "webp":
        return strip_webp(data)
    if kind == "tiff":
        return clean_tiff(data)
    raise ValueError("format d'image non reconnu")
