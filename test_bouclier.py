"""Tests unitaires automatisés pour Bouclier v2.5 (100% hors-ligne)."""
import io
try:
    import pytest
except ImportError:
    pytest = None

from bouclier import ner_engine, ocr_engine, redact, scam


def test_name_and_address_detection():
    text = (
        "Monsieur Jean Dupont habite au 14 rue de la Paix 75001 Paris. "
        "Vous pouvez contacter Madame Marie Curie au 06 12 34 56 78."
    )
    res = redact.redact(text)
    redacted = res["redacted"]
    assert "Jean Dupont" not in redacted
    assert "14 rue de la Paix" not in redacted
    assert "Marie Curie" not in redacted
    assert "06 12 34 56 78" not in redacted


def test_iban_luhn_nir_checksums():
    assert redact.iban_ok("FR7630006000011234567890189") is True
    assert redact.luhn_ok("4532015112830366") is True
    assert redact.luhn_ok("4532015112830367") is False


def test_custom_patterns_and_keywords(tmp_path=None):
    import tempfile
    from pathlib import Path
    from bouclier import ner_engine
    reg = ner_engine.registry
    old_path = reg.config_path
    reg.config_path = Path(tempfile.mkdtemp()) / "p.json"
    reg.load()
    try:
        assert reg.add_custom_pattern("Dossier", r"DOS-\d{4}") is True
        assert reg.add_custom_pattern("Casse", "([") is False
        assert reg.add_custom_pattern("Vide", "a*") is False
        assert reg.add_keyword("Projet Phoenix") is True
        out = redact.redact("Voir DOS-1234 pour le projet phoenix.")["redacted"]
        assert "DOS-1234" not in out and "phoenix" not in out.lower()
    finally:
        reg.config_path = old_path
        reg.load()


def test_manual_boxes_are_blacked_out():
    from PIL import Image
    img = Image.new("RGB", (200, 100), "white")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    res = ocr_engine.detect_and_redact_image(buf.getvalue(), extra_boxes=[(10, 10, 60, 40)], auto_detect=False)
    out = Image.open(io.BytesIO(res["data"])).convert("RGB")
    assert out.getpixel((30, 25)) == (0, 0, 0)
    assert out.getpixel((150, 80)) == (255, 255, 255)


def test_cleaner_removes_exif():
    from PIL import Image
    from bouclier import cleaner
    img = Image.new("RGB", (50, 50), "white")
    exif = Image.Exif()
    exif[0x010F] = "CamCorp"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    res = cleaner.clean_file("a.jpg", buf.getvalue())
    assert len(Image.open(io.BytesIO(res["data"])).getexif()) == 0
    assert res["found"]


def test_invoice_style_text():
    text = ("Facturé à : Martin Dupont 24 chemin des Sources 34000 Montpellier France Désignation "
            "IBAN : FR76 3000 3048 2200 0201 4567 890 BIC : SOGEFRPP SIRET : 832 456 789 00021")
    red = redact.redact(text)["redacted"]
    for secret in ("Martin Dupont", "24 chemin des Sources", "FR76 3000", "SOGEFRPP", "832 456 789"):
        assert secret not in red, secret
    assert "France Désignation" in red  # pas de debordement de l'adresse


if __name__ == "__main__":
    test_invoice_style_text()
    test_name_and_address_detection()
    test_iban_luhn_nir_checksums()
    test_custom_patterns_and_keywords()
    test_manual_boxes_are_blacked_out()
    test_cleaner_removes_exif()
    print("Tous les tests Bouclier v2.5 sont validés avec succès !")


def test_scam_detects_multiple_phishing_signals():
    result = scam.analyze("URGENT : votre colis est bloqué. Payez 2 euros sous 24h : https://bit.ly/exemple")
    assert result["score"] >= 45
    assert len(result["reasons"]) >= 3
    assert result["level"] in ("high", "critical")


def test_scam_does_not_flag_plain_message_as_high_risk():
    result = scam.analyze("Bonjour, notre réunion est prévue demain à 15h.")
    assert result["score"] < 25
