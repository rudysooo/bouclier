"""Analyseur local de signaux d'arnaque/phishing. Le score est indicatif, pas une preuve."""
from __future__ import annotations
import re
import unicodedata

RULES = [
    ("urgency", 16, r"\b(?:urgent(?:e|ement)?|immédiat(?:ement)?|sous\s+\d+\s*(?:h|heure|heures|min|minutes)|dernier\s+avertissement|expire aujourd'hui)\b", "Pression temporelle ou menace d'urgence"),
    ("credential", 28, r"\b(?:mot\s+de\s+passe|identifiants?|se\s+connecter|confirmer\s+(?:votre\s+)?compte|vérifier\s+(?:votre\s+)?compte|code\s+(?:de\s+)?vérification|code\s+secret|otp)\b", "Demande d’identifiants ou de code de sécurité"),
    ("payment", 24, r"\b(?:payer|paiement|régler|frais|carte\s+bancaire|coordonnées\s+bancaires|virement|remboursement)\b", "Demande d’argent ou de données de paiement"),
    ("delivery", 20, r"\b(?:colis|livraison|chronopost|colissimo|mondial\s+relay|poste|douane)\b", "Prétexte de livraison ou de colis"),
    ("authority", 18, r"\b(?:banque|impôts|ameli|caf|police|gendarmerie|service\s+public|support\s+technique|votre\s+conseiller)\b", "Usurpation possible d’une organisation connue"),
    ("threat", 20, r"\b(?:suspendu|bloqué|fermeture\s+du\s+compte|poursuites|amende|sanction|activité\s+suspecte)\b", "Menace de blocage, sanction ou perte d’accès"),
    ("prize", 20, r"\b(?:vous\s+avez\s+gagné|gagnant|cadeau\s+gratuit|récompense|lot\s+à\s+réclamer)\b", "Promesse de gain ou de récompense"),
    ("remote", 20, r"\b(?:anydesk|teamviewer|accès\s+à\s+distance|installer\s+ce\s+logiciel|partagez\s+votre\s+écran)\b", "Demande d’accès à distance à l’appareil"),
    ("crypto", 18, r"\b(?:crypto(?:monnaie)?|bitcoin|wallet|portefeuille\s+numérique|rendement\s+garanti|investissement\s+garanti)\b", "Promesse financière ou demande liée aux cryptomonnaies"),
]
# Arnaques au compte formation, et équivalents anglais des signaux ci-dessus (mêmes poids).
RULES += [
    ("training", 20, r"\b(?:cpf|compte\s+(?:personnel\s+de\s+)?formation|droits?\s+(?:à\s+la\s+)?formation)\b", "Prétexte de compte formation (CPF)"),
    ("expiry", 16, r"\b(?:expir(?:e|er|ent|era|eront|ation)|avant\s+(?:expiration|suppression)|perdre\s+(?:vos|votre))\b", "Menace d’expiration ou de perte de vos droits"),
    ("urgency_en", 16, r"\b(?:urgent(?:ly)?|immediately|act\s+now|final\s+(?:notice|warning)|within\s+\d+\s*(?:hours?|minutes?)|expires?\s+(?:today|soon))\b", "Pression temporelle ou menace d'urgence"),
    ("credential_en", 28, r"\b(?:password|log\s?in|sign\s?in|(?:verify|confirm|update)\s+your\s+(?:account|identity|details|information)|verification\s+code|security\s+code)\b", "Demande d’identifiants ou de code de sécurité"),
    ("payment_en", 24, r"\b(?:pay(?:ment)?|fees?|credit\s+card|bank(?:ing)?\s+details|wire\s+transfer|refund|gift\s+cards?)\b", "Demande d’argent ou de données de paiement"),
    ("delivery_en", 20, r"\b(?:parcel|package|delivery|shipment|customs)\b", "Prétexte de livraison ou de colis"),
    ("threat_en", 20, r"\b(?:suspended|locked|blocked|terminated|legal\s+action|penalty|suspicious\s+activity|unusual\s+activity)\b", "Menace de blocage, sanction ou perte d’accès"),
    ("prize_en", 20, r"\b(?:you(?:'ve|\s+have)?\s+won|winner|free\s+gift|claim\s+your\s+(?:prize|reward))\b", "Promesse de gain ou de récompense"),
]
URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>]+", re.I)
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "rb.gy", "ow.ly", "shorturl.at"}


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return text.replace("’", "'")


def analyze(text: str) -> dict:
    text = _norm(text)
    score = 0
    reasons = []
    for _key, weight, pattern, label in RULES:
        # un même signal trouvé en deux langues n'est compté qu'une fois
        if re.search(pattern, text, re.I) and all(r["text"] != label for r in reasons):
            score += weight
            reasons.append({"weight": weight, "text": label})
    urls = URL_RE.findall(text)
    if urls:
        score += min(12, 6 + 2 * (len(urls) - 1))
        reasons.append({"weight": min(12, 6 + 2 * (len(urls) - 1)), "text": "Lien présent : vérifier soigneusement le domaine"})
        if any(any(short in u.lower() for short in SHORTENERS) for u in urls):
            score += 14
            reasons.append({"weight": 14, "text": "Lien raccourci qui masque la destination réelle"})
        if any(re.search(r"https?://[^/]*(?:xn--|\d{1,3}\.\d{1,3}\.\d{1,3})", u, re.I) for u in urls):
            score += 18
            reasons.append({"weight": 18, "text": "Domaine potentiellement trompeur ou adresse IP directe"})
    if re.search(r"€|[$£]\s?\d|\b(?:eur|euros?)\b", text, re.I) and re.search(r"\d", text):
        score += 8
        reasons.append({"weight": 8, "text": "Montant d’argent mentionné"})
    if re.search(r"\b(?:ne\s+partagez\s+jamais|ne\s+communiquez\s+jamais)\b", text, re.I):
        # legitimate safety advice is a weak counter-signal, not proof of legitimacy
        score = max(0, score - 8)
    score = min(100, score)
    level = "critical" if score >= 70 else "high" if score >= 45 else "medium" if score >= 25 else "low"
    labels = {"critical": "Très suspect", "high": "Suspect", "medium": "Quelques signaux à vérifier", "low": "Peu de signaux détectés"}
    advice = [
        "Ne cliquez pas sur un lien et n’ouvrez pas de pièce jointe inattendue.",
        "Ne communiquez jamais mot de passe, code à usage unique ou données bancaires.",
        "Contactez l’organisme par son application ou son site officiel saisi manuellement.",
        "Le score est indicatif : un message légitime peut contenir ces signaux et une arnaque peut passer inaperçue.",
    ]
    return {"score": score, "level": level, "label": labels[level], "reasons": reasons, "advice": advice}
