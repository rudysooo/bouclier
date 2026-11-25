"""Algorithme avancé de détection et masquage d'informations sensibles (Bouclier v2.5)."""
from __future__ import annotations

import re
import sys
from typing import Dict, List, Set, Tuple

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<![\d.])(?:(?:\+|00)33[\s.-]?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)")
PHONE_INTL_RE = re.compile(r"(?<!\w)\+(?:[1-9]\d{0,2})[\s.-]?(?:\(?\d{1,4}\)?[\s.-]?)?\d{2,4}[\s.-]?\d{2,4}[\s.-]?\d{0,4}(?!\d)")
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b", re.IGNORECASE)
# Longueur officielle de l'IBAN par pays (évite de ne masquer qu'une partie du numéro).
IBAN_LENGTHS = {"AD": 24, "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20,
                "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26, "IT": 27,
                "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MA": 28, "MC": 27, "MT": 31, "NL": 18, "NO": 15, "PL": 28,
                "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27, "TN": 24, "TR": 26}
CARD_RE = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")  # finit toujours par un chiffre
NIR_RE = re.compile(r"(?<!\d)[12][ ]?\d{2}[ ]?(?:0[1-9]|1[0-2]|[2-9]\d)[ ]?(?:\d{2}|2[AB])[ ]?\d{3}[ ]?\d{3}(?:[ ]?\d{2})?(?!\d)")
IPV4_RE = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")

STREET_TYPES = r"rue|avenue|av\.?|bd|bld|boulevard|allée|allee|impasse|place|quai|chemin|route|square|voie|ruelle|cour|sentier|cours|passage"
_CAP = r"[A-ZÀ-ÖØ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*"
_LINK = r"(?:(?i:de\s+la|de\s+l['’]|des|du|de|d['’]|et|la|le|les|l['’])\s*)"
_CITY = rf"{_CAP}(?:-{_CAP})*(?:\s+(?:sur|sous|en|lès|les)\s+{_CAP}(?:-{_CAP})*)?"
ADDRESS_RE = re.compile(
    rf"\b\d{{1,4}}(?:\s*(?:bis|ter|quater))?(?:\s*,\s*|\s+)(?i:{STREET_TYPES})\s+{_LINK}*{_CAP}(?:\s+{_LINK}?{_CAP}){{0,3}}"
    rf"(?:\s*,?\s*\d{{5}}\s+(?:(?:Saint|Sainte|Le|La|Les|L['’])\s*)?{_CITY})?"
)
# Adresses écrites en minuscules. Les mots courants arrêtent la capture ; les types de voie ambigus
# (« place », « cours »…) exigent « de la / du / des » ou un code postal.
_STRONG_TYPES = r"rue|avenue|av\.|av|bd|bld|boulevard|allée|allee|impasse|quai|ruelle"
_WEAK_TYPES = r"place|chemin|route|square|voie|cours|cour|sentier|passage"
_LOW_STOP = (r"(?:et|ou|à|au|aux|pour|est|sont|chez|dans|avec|sans|merci|svp|puis|mais|car|depuis|vers|demain|aujourd"
             r"|hier|ce|cette|mon|ma|je|il|elle|nous|vous|on|qui|que|quand|entre|lundi|mardi|mercredi|jeudi|vendredi"
             r"|samedi|dimanche|tel|tél|mail|email|iban|bonjour|code)")
_LOW_WORD = rf"(?!{_LOW_STOP}\b)[a-zà-öø-ÿ]+(?:[-'’][a-zà-öø-ÿ]+)*"
_LOW_LINK = r"(?:(?:de[ \t]+la|de[ \t]+l['’]|des|du|de|d['’]|la|le|les|l['’]|aux)[ \t]*)"
_LOW_NAME = rf"{_LOW_LINK}*{_LOW_WORD}(?:[ \t]+{_LOW_LINK}*{_LOW_WORD}){{0,3}}"
_ANY_CITY = (r"\s*,?\s*\d{5}[ \t]+[A-Za-zÀ-ÖØ-öø-ÿ]+(?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*"
             r"(?:[ \t]+(?:sur|sous|en|lès|les)[ \t]+[A-Za-zÀ-ÖØ-öø-ÿ\-]+)?")
_NUMBER = r"\b\d{1,4}(?:[ \t]*(?:bis|ter|quater))?(?:[ \t]*,[ \t]*|[ \t]+)"
ADDRESS_LOWER_RE = re.compile(
    rf"{_NUMBER}(?:"
    rf"(?i:{_STRONG_TYPES})\b[ \t]*{_LOW_NAME}(?:{_ANY_CITY})?"
    rf"|(?i:{_WEAK_TYPES})\b[ \t]+(?:(?=de[ \t]+l|des\b|du\b){_LOW_NAME}(?:{_ANY_CITY})?|{_LOW_NAME}{_ANY_CITY})"
    rf")(?![\wÀ-ÿ])"
)
POSTAL_CODE_CITY_RE = re.compile(rf"\b\d{{5}}\s+(?:(?:Saint|Sainte|Le|La|Les)\s+)?{_CITY}\b")

HONORIFICS = r"(?:Monsieur|Madame|Mademoiselle|M\.|Mme|Mlle|Dr\.?|Docteur|Me|Maître|Maitre|Professeur|Pr\.?|Directeur|Directrice|Président|Présidente)"
HONORIFIC_NAME_RE = re.compile(
    rf"\b{HONORIFICS}\s+([A-ZÀ-ÖØ][a-zà-öø-ÿ]+(?:[-'\s][A-ZÀ-ÖØ][a-zà-öø-ÿ]+){{1,3}})\b"
)
KEYWORD_NAME_RE = re.compile(
    r"\b(?:Nom\s*:\s*|Prénom\s*:\s*|Auteur\s*:\s*|Signé\s*:\s*|De\s*:\s*|À\s*:\s*|Contact\s*:\s*|Titulaire\s*:\s*|Patient\s*:\s*|Client\s*:\s*)([A-ZÀ-ÖØ][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ][a-zà-öø-ÿ]+){1,2})"
)
BILLING_NAME_RE = re.compile(
    r"(?:Factur[ée]e?\s+[àaA]|Adresse\s+de\s+livraison|Livr[ée]e?\s+[àa]|Destinataire|Exp[ée]diteur|Bénéficiaire|Beneficiaire|Titulaire|Nom\s+du\s+client|Client)"
    r"\s*:?\s+(?:(?:M\.|Mme|Mlle|Monsieur|Madame)\s+)?([A-ZÀ-ÖØ][a-zà-öø-ÿ'’\-]+(?:\s+[A-ZÀ-ÖØ][a-zà-öø-ÿ'’\-]+){1,2})"
)
SIRET_RE = re.compile(r"(?i:SIRET|SIREN|N°\s*TVA|TVA\s+intracom\w*)\s*:?\s*((?:[A-Z]{2}\s?)?\d[\d ]{7,18}\d)")
BIC_RE = re.compile(r"(?i:\bBIC|\bSWIFT)\s*:?\s*([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b")
CLOSING_NAME_RE = re.compile(
    r"(?:Cordialement|Bien\s+cordialement|Bien\s+à\s+vous|Sincères\s+salutations|Amitiés|Respectueusement)[,\s\n]+([A-ZÀ-ÖØ][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ][a-zà-öø-ÿ]+){1,2})"
)

COMMON_FIRSTNAMES = {
    "jean", "marie", "pierre", "michel", "thomas", "lucas", "louis", "gabriel", "arthur", "jules",
    "leo", "hugo", "nathan", "paul", "emma", "lea", "chloe", "manon", "camille", "sarah",
    "julie", "marine", "laura", "alexandre", "nicolas", "julien", "maxime", "antoine", "romain",
    "florian", "guillaume", "kevin", "jeremy", "clement", "clément", "david", "sebastien", "sébastien",
    "sophie", "celine", "céline", "aurelie", "aurélie", "elodie", "élodie", "stephanie", "stéphanie",
    "laurent", "philippe", "alain", "christophe", "patrick", "daniel", "bernard", "christian",
    "francois", "françois", "marc", "vincent", "eric", "éric", "bruno", "pascal", "frederic", "frédéric",
    "valerie", "valérie", "sandrine", "isabelle", "nathalie", "catherine", "sylvie", "martine",
    "francoise", "françoise", "monique", "nicole", "anne", "claire", "helene", "hélène", "lucie", "charlotte",
    "martin", "robert", "andre", "andré", "henri", "jacques", "gerard", "gérard", "yves", "denis", "didier", "jerome", "jérôme",
    "olivier", "fabrice", "stephane", "stéphane", "thierry", "franck", "cedric", "cédric", "mathieu", "benjamin", "adrien",
    "yann", "joseph", "georges", "rene", "rené", "claude", "joel", "joël", "mohamed", "karim", "ahmed", "youssef",
    "ines", "inès", "amelie", "amélie", "melanie", "mélanie", "audrey", "emilie", "émilie", "virginie", "caroline", "delphine",
    "mathilde", "pauline", "margaux", "juliette", "alice", "louise", "jeanne", "agnes", "agnès", "brigitte", "dominique",
    "adam", "aaron", "alexis", "amine", "anthony", "arnaud", "aurelien", "aurélien", "baptiste", "bastien", "benoit",
    "benoît", "boris", "bryan", "cyril", "damien", "dorian", "dylan", "elias", "emile", "émile", "enzo", "erwan",
    "ethan", "evan", "fabien", "gael", "gaël", "gaetan", "gaëtan", "gilles", "gregory", "grégory", "guy", "hamza",
    "herve", "hervé", "ibrahim", "ilyes", "isaac", "jonathan", "jordan", "julian", "kylian", "léo", "liam", "loic",
    "loïc", "lorenzo", "louka", "mael", "maël", "marius", "mathis", "matthieu", "mattéo", "matteo", "maurice",
    "mehdi", "mickael", "mickaël", "nael", "naël", "noah", "noé", "omar", "quentin", "raphael", "raphaël", "rayan",
    "remi", "rémi", "remy", "rémy", "robin", "roger", "samuel", "sami", "serge", "simon", "steven", "sylvain",
    "theo", "théo", "timothee", "timothée", "tom", "tristan", "valentin", "victor", "william", "xavier", "yanis",
    "yohan", "yoann", "zacharie", "ali", "mustapha", "rachid", "said", "saïd", "samir", "sofiane", "bilal",
    "adele", "adèle", "agathe", "aicha", "aïcha", "alexandra", "alexia", "alicia", "alix", "amandine", "ambre",
    "anais", "anaïs", "andrea", "angelique", "angélique", "anna", "annie", "ariane", "aurore", "axelle", "barbara",
    "beatrice", "béatrice", "bérénice", "capucine", "carole", "cecile", "cécile", "chantal", "charline", "christelle",
    "christine", "clara", "clemence", "clémence", "coralie", "corinne", "danielle", "deborah", "déborah", "diane",
    "elisa", "élisa", "elisabeth", "élisabeth", "eloise", "éloïse", "elsa", "emeline", "émeline", "estelle", "eva",
    "fanny", "fatima", "fatoumata", "flavie", "florence", "gaelle", "gaëlle", "genevieve", "geneviève", "gwendoline",
    "ines", "irene", "irène", "jade", "jessica", "joelle", "joëlle", "josiane", "justine", "karine", "khadija",
    "laetitia", "laëtitia", "lena", "léna", "lola", "lou", "louna", "ludivine", "maelys", "maëlys", "magali",
    "maeva", "maëva", "marion", "marjorie", "maud", "maureen", "mélissa", "melissa", "michele", "michèle", "mylene",
    "mylène", "myriam", "nadia", "nadine", "nina", "noemie", "noémie", "oceane", "océane", "odile", "olivia",
    "pascale", "patricia", "rachel", "romane", "rose", "sabrina", "salome", "salomé", "samia", "sara", "severine",
    "séverine", "solene", "solène", "sonia", "suzanne", "vanessa", "veronique", "véronique", "victoria", "yasmine",
    "yvette", "zoe", "zoé", "john", "james", "michael", "peter", "mary", "jennifer", "sarah", "carlos", "maria",
    "juan", "jose", "josé", "pablo", "lucia", "lucía", "sofia", "sofía"
}

STOPWORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "dans", "pour", "avec", "sans", "sur",
    "france", "paris", "lyon", "marseille", "bordeaux", "toulouse", "lille", "nantes", "strasbourg",
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche", "janvier", "fevrier",
    "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre",
    "bonjour", "merci", "veuillez", "cordialement", "objet", "facture", "contrat", "société",
    "banque", "service", "assurance", "compte", "numéro", "client", "adresse", "dossier", "document"
}

# Mots courants qui ne sont jamais pris pour un prénom ou un nom par les règles contextuelles.
NOT_NAME = STOPWORDS | set("""
a à au aux ce cet cette ces mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs je tu il elle on nous
vous ils elles qui que quoi dont où et ou mais donc or ni car si quand comme par sous chez vers entre depuis voir
bonsoir salut coucou cher chère chers chères monsieur madame mademoiselle mme mlle me maître docteur président
présidente directeur directrice professeur nom prénom prenom nom date lieu total montant prix référence reference page
annexe article chapitre section titre version fichier format envoi réception commande livraison paiement règlement
virement formulaire attestation certificat rapport note avis conditions attention important urgent information
informations info infos menu aide site projet groupe équipe direction agence bureau centre hôtel hotel gare aéroport
musée parc europe code carte numero type taille modèle modele produit offre solde remise guide notice manuel liste
tableau figure image photo copie original signature signé madame monsieur tous toutes tout toute chaque aucun aucune
oui non ici voici voilà alors aussi très plus moins bien notre vôtre nôtre office windows android linux python
january february march april monday friday the this that your our dear hello hi please new see all world team sir
madam client cliente patient patiente locataire propriétaire titulaire entreprise société inconnu anonyme néant aucun
général générale adjoint adjointe principal principale technique commercial commerciale amis ami amie toi
""".split())
# Sigles fréquents écrits en majuscules (à ne pas confondre avec un nom de famille).
ACRONYMS = set("""
iban bic swift siret siren tva rib sepa sncf ratp edf engie caf cpam ameli urssaf pdf jpeg png sms mms url http https
www usb wifi sim cdi cdd rtt pdg tgv ter rer ttc eur usd gbp chf cni nir faq cgu cgv rgpd cnil insee ursaf smic apl
rsa aah ccp livret mutuelle assurance banque confidentiel attention important urgent merci total annexe facture
contrat document client service objet france paris europe offre spécial speciale gratuit nouveau promo vente achat
travail emploi information informations conditions générales generales article titre dossier numéro numero adresse
téléphone telephone email mail date nom prénom prenom madame monsieur sas sarl eurl sci asso association mairie
préfecture prefecture ministère ministere université universite école ecole lycée lycee hôpital hopital server
""".split())

_PARTICLES = {"de", "du", "des", "le", "la", "van", "von", "da", "el", "ben"}
_NAME_WORD = r"[A-ZÀ-ÖØ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*"
_NEXT_CAP = re.compile(rf"[ \t]*((?:(?:de|du|des|le|la|van|von|da|el|ben)[ \t]+(?=[A-ZÀ-ÖØ])){{0,3}}{_NAME_WORD})")
_NEXT_ANY = re.compile(r"[ \t]*([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*)")
# « Nom : … », « Prénom : … » : le libellé suffit, quelle que soit la casse de la valeur.
NAME_LABEL_RE = re.compile(
    r"(?i:\b(?:nom(?:\s+et\s+pr[ée]nom|\s+de\s+famille|\s+complet|\s+d['’]usage|\s+de\s+naissance)?"
    r"|pr[ée]noms?(?:\s+et\s+nom)?|signataire|locataire|propri[ée]taire|patiente?|titulaire))[ \t]*:")
INTRO_NAME_RE = re.compile(r"(?i:\bje\s+m['’]appelle|\bmon\s+nom\s+est|\bje\s+soussign[ée](?:\(e\))?[ \t]*,?)")
GREETING_RE = re.compile(r"(?i:\b(?:bonjour|bonsoir|salut|coucou|cher|chère|hello|dear|hola))\b")
CIVILITY_RE = re.compile(r"\b(?:Monsieur|Madame|Mademoiselle|M\.|Mme|Mlle|Mr|Mrs|Dr\.?|Docteur|Maître|Maitre)(?=[ \t])")
_FIRST = r"[A-ZÀ-ÖØ][a-zà-öø-ÿ]+(?:-[A-ZÀ-ÖØ][a-zà-öø-ÿ]+)?"
_SURNAME = r"(?:(?:DE|DU|DES|LE|LA|VAN|VON|DA|EL|BEN|AL)[ '’]){0,3}[A-ZÀ-ÖØ]{2,}(?:[-'’][A-ZÀ-ÖØ]+)*"
# « Zéphyrine QUILLARD » et « QUILLARD Zéphyrine » : l'usage administratif français.
FIRST_SURNAME_RE = re.compile(rf"(?<![\wÀ-ÿ])({_FIRST})[ \t]+({_SURNAME})((?:[ \t]+{_SURNAME})?)(?![\wÀ-ÿ])")
SURNAME_FIRST_RE = re.compile(rf"(?<![\wÀ-ÿ])({_SURNAME})[ \t]+({_FIRST})(?![\wÀ-ÿ])")

LABELS = {
    "name": "Nom & Prénom",
    "email": "Adresse e-mail",
    "phone": "Téléphone",
    "address": "Adresse postale",
    "iban": "IBAN",
    "card": "Carte bancaire",
    "nir": "N° de sécurité sociale",
    "ip": "Adresse IP",
    "custom": "Motifs perso",
}


def luhn_ok(digits: str) -> bool:
    clean = re.sub(r"\D", "", digits)
    if not (13 <= len(clean) <= 19):
        return False
    total, alt = 0, False
    for ch in reversed(clean):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def iban_ok(raw: str) -> bool:
    s = raw.replace(" ", "").upper()
    if not 15 <= len(s) <= 34:
        return False
    rearranged = s[4:] + s[:4]
    try:
        num = "".join(str(int(c, 36)) for c in rearranged)
        return int(num) % 97 == 1
    except ValueError:
        return False


def nir_ok(raw: str) -> bool:
    s = raw.replace(" ", "").upper()
    if len(s) == 13:
        return True
    if len(s) != 15:
        return False
    try:
        body = s[:13].replace("2A", "19").replace("2B", "18")
        key = int(s[13:])
        return 97 - (int(body) % 97) == key
    except ValueError:
        return False


def _name_hit(text: str, start: int, end: int) -> Dict:
    return {"type": "name", "label": LABELS["name"], "start": start, "end": end, "value": text[start:end]}


def _words_after(text: str, pos: int, limit: int, any_case: bool = False):
    """Position (début, fin) des mots de nom qui suivent `pos` sur la même ligne, ou None."""
    pattern = _NEXT_ANY if any_case else _NEXT_CAP
    start = end = first = None
    count = steps = 0
    while count < limit and steps < 3 * limit:
        steps += 1
        m = pattern.match(text, pos)
        if not m:
            break
        last = m.group(1).split()[-1]
        if last.lower() in _PARTICLES and last[:1].isupper():
            # « LE GALL », « de LA FONTAINE » : la particule ne compte que suivie d'un nom
            following = pattern.match(text, m.end(1))
            if following and following.group(1).split()[-1].lower() not in NOT_NAME:
                first = m.start(1) if first is None else first
                pos = m.end(1)
                continue
            break
        if last.lower() in NOT_NAME:
            break
        first = m.start(1) if first is None else first
        start, end = first, m.end(1)
        pos, count = end, count + 1
    return None if start is None else (start, end)


def _is_surname(word: str) -> bool:
    low = word.lower()
    return (len(low) >= 3 and any(c in "aeiouyàâäéèêëîïôöùûü" for c in low)
            and low not in ACRONYMS and low not in NOT_NAME)


def _contextual_names(text: str) -> List[Dict]:
    names = []
    for rule, limit, any_case in ((NAME_LABEL_RE, 3, True), (INTRO_NAME_RE, 3, False),
                                  (GREETING_RE, 3, False), (CIVILITY_RE, 4, False)):
        for m in rule.finditer(text):
            span = _words_after(text, m.end(), limit, any_case)
            if span:
                names.append(_name_hit(text, *span))

    for m in FIRST_SURNAME_RE.finditer(text):
        if m.group(1).lower() in NOT_NAME or not _is_surname(m.group(2)):
            continue
        extra = m.group(3).strip()
        names.append(_name_hit(text, m.start(1), m.end(3) if extra and _is_surname(extra) else m.end(2)))
    for m in SURNAME_FIRST_RE.finditer(text):
        before = text[max(0, m.start() - 60):m.start()].rstrip(" \t").rsplit(None, 1)
        if before and len(before[-1]) > 1 and before[-1].isupper():
            continue  # titre entièrement en majuscules, pas un nom de famille
        if m.group(2).lower() in NOT_NAME or not _is_surname(m.group(1)):
            continue
        names.append(_name_hit(text, m.start(1), m.end(2)))
    return names


def extract_names(text: str) -> List[Dict]:
    names = _contextual_names(text)
    for m in HONORIFIC_NAME_RE.finditer(text):
        full = m.group(0)
        name_part = m.group(1)
        start = m.start() + full.find(name_part)
        names.append({"type": "name", "label": LABELS["name"], "start": start, "end": start + len(name_part), "value": name_part})

    for m in KEYWORD_NAME_RE.finditer(text):
        name_part = m.group(1)
        start = m.start() + m.group(0).find(name_part)
        names.append({"type": "name", "label": LABELS["name"], "start": start, "end": start + len(name_part), "value": name_part})

    for m in BILLING_NAME_RE.finditer(text):
        name_part = m.group(1)
        if name_part.split()[0].lower() in STOPWORDS:
            continue
        start = m.start() + m.group(0).rfind(name_part)
        names.append({"type": "name", "label": LABELS["name"], "start": start, "end": start + len(name_part), "value": name_part})

    for m in CLOSING_NAME_RE.finditer(text):
        name_part = m.group(1)
        start = m.start() + m.group(0).find(name_part)
        names.append({"type": "name", "label": LABELS["name"], "start": start, "end": start + len(name_part), "value": name_part})

    tokens = re.split(r"([^\wÀ-ÖØ-öø-ÿ'-]+)", text)
    pos = 0
    for i in range(0, len(tokens) - 2, 2):
        w1 = tokens[i]
        sep = tokens[i + 1]
        w2 = tokens[i + 2]
        low1 = w1.lower()
        if low1 in COMMON_FIRSTNAMES and sep == " " and w1[:1].isupper() and w2[:1].isupper():
            if w2.lower() not in STOPWORDS and len(w2) >= 2:
                start = pos
                val = f"{w1} {w2}"
                names.append({"type": "name", "label": LABELS["name"], "start": start, "end": start + len(val), "value": val})
        pos += len(w1) + len(sep)

    return names


def _iban_span(text: str, m) -> int:
    """Fin du numéro IBAN trouvé par `m` (sans les mots qui le suivent), ou -1 si ce n'en est pas un."""
    raw = m.group(0)
    ends = [i for i, ch in enumerate(raw) if ch == " "] + [len(raw)]
    expected = IBAN_LENGTHS.get(raw[:2].upper())
    for end in reversed(ends):
        compact = raw[:end].replace(" ", "")
        if (expected is None or len(compact) == expected) and iban_ok(compact):
            return m.start() + end
    # IBAN mal lu (OCR) : forme française complète, ou précédé du mot « IBAN ».
    # Mieux vaut masquer un faux positif que laisser fuiter un numéro.
    if raw[:2].upper() == "FR":
        for end in ends:
            if len(raw[:end].replace(" ", "")) == 27:
                return m.start() + end
    if re.search(r"(?i)iban\W{0,6}$", text[max(0, m.start() - 12):m.start()]):
        tokens = raw.split(" ")
        while len(tokens) > 1 and not any(c.isdigit() for c in tokens[-1]) and not tokens[-1].isupper():
            tokens.pop()
        return m.start() + len(" ".join(tokens))
    return -1


def _card_span(m) -> int:
    """Fin du numéro de carte (en écartant d'éventuels chiffres voisins), ou -1."""
    raw = m.group(0)
    ends = [len(raw)] + [i for i in range(len(raw) - 1, 0, -1) if raw[i] in " -"]
    return next((m.start() + end for end in ends if luhn_ok(raw[:end])), -1)


def find_sensitive(text: str, enabled_types: Set[str] | None = None) -> List[Dict]:
    hits = []
    def should_add(k): return enabled_types is None or k in enabled_types
    def add(kind, m, val=None): hits.append({"type": kind, "label": LABELS.get(kind, kind), "start": m.start(), "end": m.end(), "value": val or m.group(0)})

    def add_span(kind, start, end):
        hits.append({"type": kind, "label": LABELS.get(kind, kind), "start": start, "end": end, "value": text[start:end]})

    if should_add("iban"):
        for m in IBAN_RE.finditer(text):
            end = _iban_span(text, m)
            if end > 0:
                add_span("iban", m.start(), end)
        for m in BIC_RE.finditer(text):
            hits.append({"type": "iban", "label": "BIC / SWIFT", "start": m.start(1), "end": m.end(1), "value": m.group(1)})
        for m in SIRET_RE.finditer(text):
            hits.append({"type": "iban", "label": "SIRET / TVA", "start": m.start(1), "end": m.end(1), "value": m.group(1)})
    if should_add("nir"):
        for m in NIR_RE.finditer(text):
            if nir_ok(m.group(0)): add("nir", m)
    if should_add("card"):
        for m in CARD_RE.finditer(text):
            end = _card_span(m)
            if end > 0: add_span("card", m.start(), end)
    if should_add("email"):
        for m in EMAIL_RE.finditer(text): add("email", m)
    if should_add("phone"):
        for m in PHONE_RE.finditer(text): add("phone", m)
        for m in PHONE_INTL_RE.finditer(text):
            val = m.group(0).rstrip(" \t\r\n.-(")  # ne pas avaler l'espace ou le point qui suit
            if len(re.sub(r"\D", "", val)) >= 8: add_span("phone", m.start(), m.start() + len(val))
    if should_add("address"):
        for m in ADDRESS_RE.finditer(text): add("address", m, m.group(0).strip())
        for m in ADDRESS_LOWER_RE.finditer(text): add("address", m)
        for m in POSTAL_CODE_CITY_RE.finditer(text): add("address", m)
    if should_add("ip"):
        for m in IPV4_RE.finditer(text): add("ip", m)
    if should_add("name"):
        for item in extract_names(text): hits.append(item)
    if should_add("custom"):
        from . import ner_engine
        hits.extend(ner_engine.registry.find_custom(text))

    hits.sort(key=lambda h: (h["start"], -(h["end"] - h["start"])))
    result = []
    last_end = -1
    for h in hits:
        if h["start"] >= last_end:
            result.append(h)
            last_end = h["end"]
        elif h["end"] > last_end and result[-1]["type"] == h["type"] and h["type"] in ("name", "address"):
            # deux règles se chevauchent : on masque l'ensemble, jamais seulement le début
            result[-1]["end"] = last_end = h["end"]
            result[-1]["value"] = text[result[-1]["start"]:last_end]
    return result


def mask_value(kind: str, value: str, style: str = "placeholder", pseudonym_map: Dict | None = None) -> str:
    if style == "stars":
        if kind == "email":
            u, _, d = value.partition("@")
            return f"{u[:1]}•••••••@{d}"
        if kind == "name":
            return " ".join(f"{p[0]}•••••" if len(p) > 1 else "•" for p in value.split())
        if kind == "custom":
            return "•" * min(max(len(value), 3), 12)
        if kind == "address":
            return "••••• ••••• •••••"  # ni lettres, ni longueur réelle
        digits = [c for c in value if c.isalnum()]
        keep = 4 if kind in ("iban", "card") else 2
        tail = "".join(digits[-keep:])
        return f"•••• •••• •••• {tail}" if kind != "ip" else "•••.•••.•••.•••"

    if style == "pseudonym" and pseudonym_map is not None:
        key = f"{kind}:{value.strip().lower()}"
        if key not in pseudonym_map:
            counts = pseudonym_map.setdefault("__counts__", {})
            c = counts.get(kind, 0) + 1
            counts[kind] = c
            prefix = {"name": "PERSONNE", "email": "EMAIL", "phone": "TEL", "address": "ADRESSE", "iban": "COMPTE_IBAN", "card": "CARTE", "nir": "NUM_SECU", "ip": "IP", "custom": "PERSO"}.get(kind, "ENTITE")
            pseudonym_map[key] = f"[{prefix}_{c}]"
        return pseudonym_map[key]

    if kind == "email":
        u, _, d = value.partition("@")
        return f"[EMAIL •••@{d}]"
    if kind == "name":
        return "[NOM MASQUÉ]"
    if kind == "custom":
        return "[DONNÉE MASQUÉE]"
    if kind == "address":
        return "[ADRESSE POSTALE MASQUÉE]"
    digits = [c for c in value if c.isalnum()]
    keep = 4 if kind in ("iban", "card") else 2
    tail = "".join(digits[-keep:])
    return f"[{LABELS.get(kind, kind).upper()} ••••{tail}]" if kind != "ip" else "[ADRESSE IP]"


def redact(text: str, kinds: Set[str] | None = None, style: str = "placeholder") -> Dict:
    hits = find_sensitive(text, kinds)
    out = []
    pos = 0
    pseudonym_map = {}
    for h in hits:
        out.append(text[pos:h["start"]])
        rep = mask_value(h["type"], h["value"], style=style, pseudonym_map=pseudonym_map)
        h["replacement"] = rep
        out.append(rep)
        pos = h["end"]
    out.append(text[pos:])
    return {"findings": hits, "redacted": "".join(out)}
