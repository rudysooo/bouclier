"""Tests de la couche de services de la nouvelle interface (sans Qt, hors écran)."""
import io
import tempfile
from pathlib import Path

from bouclier.ui import services


class W:  # faux mot OCR
    def __init__(self, text, left, top, width=60, height=20, line=(1, 1, 1)):
        self.text, self.left, self.top, self.width, self.height, self.line_key = text, left, top, width, height, line

    right = property(lambda s: s.left + s.width)
    bottom = property(lambda s: s.top + s.height)


def test_entities_from_words_maps_boxes():
    words = [W("Écrire", 10, 10), W("à", 80, 10), W("jean.dupont@example.com", 100, 10, 200)]
    ents = services.entities_from_words(words, (400, 100))
    assert len(ents) == 1 and ents[0]["type"] == "email" and not ents[0]["excluded"]
    x0, y0, x1, y1 = ents[0]["boxes"][0]
    assert x0 <= 100 and x1 >= 300 and y0 <= 10 and y1 >= 30


def test_analyze_text_highlights_and_counts():
    r = services.analyze_text("Contact : jean@example.com", {"email"}, "placeholder")
    assert r["count"] == 1 and "jean@example.com" not in r["redacted"]
    assert "jean@example.com" in r["sourceHtml"] and "<span" in r["resultHtml"]


def test_try_pattern():
    assert services.try_pattern("DOS-\\d+", "voir DOS-12")["count"] == 1
    assert services.try_pattern("([", "x")["valid"] is False
    assert services.try_pattern("a*", "x")["valid"] is False


def test_to_local_path():
    assert services.to_local_path("file:///tmp/a%20b.png") == "/tmp/a b.png"
    assert services.to_local_path("/tmp/x.png") == "/tmp/x.png"


def test_image_roundtrip_manual_box():
    from PIL import Image
    d = tempfile.mkdtemp()
    p = Path(d) / "a.png"
    Image.new("RGB", (200, 100), "white").save(p)
    info = services.load_image(str(p), d)
    assert (info["width"], info["height"]) == (200, 100) and Path(info["preview"]).exists()
    res = services.apply_redaction(info["data"], "blackout", [[10, 10, 60, 40]])
    out = Image.open(io.BytesIO(res["data"])).convert("RGB")
    assert out.getpixel((30, 25)) == (0, 0, 0) and out.getpixel((150, 80)) == (255, 255, 255)
    assert services.suggested_name(str(p), res["format"]).endswith("a_anonymise.png")


def test_clean_path_never_overwrites():
    from PIL import Image
    d = Path(tempfile.mkdtemp())
    Image.new("RGB", (20, 20), "white").save(d / "x.png")
    a = services.clean_path(str(d / "x.png"))
    b = services.clean_path(str(d / "x.png"))
    assert a["output"] != b["output"] and Path(a["output"]).exists() and Path(b["output"]).exists()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
