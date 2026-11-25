"""Anonymisation et caviardage destructif d'images (Bouclier v2.5)."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Tuple, Union

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
except ImportError:
    Image = None


def pixelate_region(img: Image.Image, box: Tuple[int, int, int, int], pixel_size: int = 14) -> None:
    x0, y0, x1, y1 = box
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    region = img.crop((x0, y0, x1, y1))
    small_w = max(1, w // pixel_size)
    small_h = max(1, h // pixel_size)
    small = region.resize((small_w, small_h), resample=Image.Resampling.NEAREST)
    pixelated = small.resize((w, h), resample=Image.Resampling.NEAREST)
    img.paste(pixelated, (x0, y0))


def blur_region(img: Image.Image, box: Tuple[int, int, int, int], radius: int = 15) -> None:
    x0, y0, x1, y1 = box
    region = img.crop((x0, y0, x1, y1))
    blurred = region.filter(ImageFilter.GaussianBlur(radius=radius))
    blurred = blurred.filter(ImageFilter.GaussianBlur(radius=max(2, radius // 2)))
    img.paste(blurred, (x0, y0))


def blackout_region(img: Image.Image, box: Tuple[int, int, int, int], label: str = "") -> None:
    draw = ImageDraw.Draw(img)
    draw.rectangle(box, fill="#000000")
    x0, y0, x1, y1 = box
    if (x1 - x0) > 40 and (y1 - y0) > 20:
        draw.rectangle(box, outline="#222222", width=1)


def redact_image(
    source: Union[str, bytes, Path],
    boxes: List[Dict],
    mode: str = "blackout",
    output_format: str = "PNG"
) -> Tuple[bytes, List[str]]:
    if Image is None:
        raise RuntimeError("Pillow est requis.")
    if isinstance(source, bytes):
        img = Image.open(io.BytesIO(source))
    else:
        img = Image.open(source)

    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    w, h = img.size
    actions = []
    for b in boxes:
        bx = int(b.get("x", 0) * w if b.get("x", 0) <= 1.0 else b.get("x", 0))
        by = int(b.get("y", 0) * h if b.get("y", 0) <= 1.0 else b.get("y", 0))
        bw = int(b.get("width", 0) * w if b.get("width", 0) <= 1.0 else b.get("width", 0))
        bh = int(b.get("height", 0) * h if b.get("height", 0) <= 1.0 else b.get("height", 0))

        x0, y0 = max(0, bx), max(0, by)
        x1, y1 = min(w, bx + bw), min(h, by + bh)
        if x1 <= x0 or y1 <= y0:
            continue

        box_tuple = (x0, y0, x1, y1)
        bmode = b.get("redactionType", mode)
        if bmode == "pixelate":
            pixelate_region(img, box_tuple)
        elif bmode == "blur":
            blur_region(img, box_tuple)
        else:
            blackout_region(img, box_tuple)
        actions.append(f"Masqué ({x0},{y0})")

    out_buf = io.BytesIO()
    clean_canvas = Image.new("RGB" if output_format.upper() in ("JPEG", "JPG") else img.mode, img.size)
    clean_canvas.paste(img)
    if output_format.upper() in ("JPEG", "JPG"):
        clean_canvas.save(out_buf, format="JPEG", quality=95, subsampling=0)
    else:
        clean_canvas.save(out_buf, format="PNG", optimize=True)
    return out_buf.getvalue(), actions
