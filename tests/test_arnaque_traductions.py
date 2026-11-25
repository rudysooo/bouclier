"""Anti-arnaque (petits montants, CPF, anglais) et traductions des nouveaux messages."""
import pytest

from bouclier import scam


def test_small_amount_in_euro_sign_is_seen():
    reasons = [r["text"] for r in scam.analyze("Frais de 1,99 € à régler")["reasons"]]
    assert "Montant d’argent mentionné" in reasons


@pytest.mark.parametrize("message", [
    "Votre compte CPF de 1500€ expire bientôt. Activez vos droits : http://cpf-info.example",
    "URGENT: your account has been suspended. Verify your account now: http://secure.example",
    "Your parcel is on hold. Pay the $1.99 delivery fee: https://bit.ly/x",
])
def test_cpf_and_english_scams_are_not_low(message):
    assert scam.analyze(message)["level"] in ("medium", "high", "critical")


@pytest.mark.parametrize("message", ["See you tomorrow at 3pm.", "La réunion est prévue demain à 15h."])
def test_plain_messages_stay_low(message):
    assert scam.analyze(message)["level"] == "low"


@pytest.mark.parametrize("language", ["en", "es"])
def test_new_messages_are_translated(language):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from bouclier.ui import backends, services

    QApplication.instance() or QApplication([])
    app = backends.AppBackend()
    for text in ("Tesseract introuvable.", services.OCR_UNREAD_MISSING, services.OCR_FAILED_PREFIX + "x",
                 "Seuls les visages ont été recherchés : 2 repéré(s).", "Commentaires supprimés (3)",
                 "Ce fichier contient 2 pages ou images : seule la première est traitée et enregistrée.",
                 "Texte NON lu : seules 1 zone(s) (visages et zones manuelles) ont été masquées. "
                 "Vérifiez l'image avant de la partager."):
        assert app.tr(text, language) != text, text
