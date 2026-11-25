"""Détection dans le texte (minuscules, noms, carte, étoiles) et anti-arnaque."""
import time

import pytest

from bouclier import redact


def masked(text, style="placeholder"):
    return redact.redact(text, style=style)["redacted"]


@pytest.mark.parametrize("iban", [
    "fr76 3000 6000 0112 3456 7890 189", "fr7630006000011234567890189", "de89 3704 0044 0532 0130 00",
    "FR76 3000 6000 0112 3456 7890 189",
])
def test_iban_any_case_without_eating_following_words(iban):
    out = masked(f"Virement sur {iban} merci pour tout")
    assert iban not in out and "0112" not in out and "0532" not in out
    assert out.startswith("Virement sur [IBAN") and out.endswith(" merci pour tout")


@pytest.mark.parametrize("address", [
    "14 rue de la paix 75001 paris", "3 avenue victor hugo", "12 bis boulevard des capucines",
    "5 place de la mairie", "8 chemin vert 34000 montpellier", "14, rue des lilas",
])
def test_lowercase_address(address):
    out = masked(f"j'habite au {address}, à bientôt")
    assert address not in out and "[ADRESSE POSTALE MASQUÉE]" in out and out.endswith(", à bientôt")


@pytest.mark.parametrize("text", [
    "Il y a 1 chemin pour réussir.", "J'ai 2 cours de maths demain.", "Il reste 3 places pour le concert.",
    "Voir CONDITIONS GÉNÉRALES de vente.", "Notre OFFRE SPÉCIALE est disponible.", "Billet SNCF à 25 euros.",
    "Votre IBAN sera demandé.", "CONTRAT DE TRAVAIL Entre les parties.", "Bonjour Madame, merci beaucoup.",
    "Le Directeur Général arrive.", "Cher client, veuillez patienter.", "La réunion de lundi est annulée.",
])
def test_ordinary_text_is_left_alone(text):
    assert masked(text) == text


@pytest.mark.parametrize("text,secrets", [
    ("Dossier de Zéphyrine QUILLARD, né en 1990.", ["Zéphyrine", "QUILLARD"]),
    ("Dossier suivi par QUILLARD Zéphyrine.", ["QUILLARD", "Zéphyrine"]),
    ("Nom : QUILLARD", ["QUILLARD"]),
    ("Prénom : Zéphyrine", ["Zéphyrine"]),
    ("nom : quillard\nville : x", ["quillard"]),
    ("NOM : LE GALL Prénom : Maïwenn", ["LE GALL", "Maïwenn"]),
    ("Bonjour Zéphyrine, voici le devis.", ["Zéphyrine"]),
    ("Je m'appelle Zéphyrine Quillard.", ["Zéphyrine", "Quillard"]),
    ("Merci M. DUPONT pour votre venue.", ["DUPONT"]),
    ("Madame Zéphyrine de LA FONTAINE est attendue.", ["Zéphyrine", "FONTAINE"]),
    ("Contactez Jean DUPONT.", ["Jean", "DUPONT"]),
])
def test_rare_and_uppercase_names(text, secrets):
    out = masked(text)
    for secret in secrets:
        assert secret not in out, out


def test_trailing_space_after_first_name_does_not_crash():
    assert masked("Merci Jean ") == "Merci Jean "


@pytest.mark.parametrize("text,expected", [
    ("Carte 4532 0151 1283 0366 valide", "Carte [CARTE BANCAIRE ••••0366] valide"),
    ("Carte 4532015112830366 12/27", "Carte [CARTE BANCAIRE ••••0366] 12/27"),
    ("Carte 4532-0151-1283-0366.", "Carte [CARTE BANCAIRE ••••0366]."),
])
def test_card_mask_keeps_surrounding_text(text, expected):
    assert masked(text) == expected


def test_international_phone_keeps_following_space_and_dot():
    assert masked("Appelle +44 20 7946 0958 demain", "stars") == "Appelle •••• •••• •••• 58 demain"
    assert masked("Mon numéro : +44 20 7946 0958.").endswith("].")


def test_stars_style_hides_whole_address():
    out = masked("Adresse : 14 rue de la Paix 75001 Paris.", "stars")
    assert out == "Adresse : ••••• ••••• •••••."


@pytest.mark.parametrize("text", ["DE " * 20000 + "x", "M. " + "LE " * 20000, "Zoé DUPONT " * 5000],
                         ids=["particules", "civilite", "noms"])
def test_long_repetitive_text_stays_fast(text):
    start = time.perf_counter()
    redact.redact(text)
    assert time.perf_counter() - start < 5
