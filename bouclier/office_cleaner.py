"""Nettoyage des documents Word / Excel / PowerPoint (OOXML), 100 % local.

La copie nettoyée correspond à la version FINALE du document :
- métadonnées (auteur, société, titre…) vidées ;
- suivi des modifications accepté : le texte supprimé disparaît, plus aucun nom ni date ;
- commentaires, listes d'auteurs (people.xml…) et historiques de révision supprimés ;
- vignette d'aperçu supprimée ; EXIF / GPS retirés des images internes.
"""
from __future__ import annotations

import io
import posixpath
import re
import zipfile
from urllib.parse import unquote
from xml.dom import Node, minidom

from . import image_meta
from .cleaner import CleanError

_CORE_BLANK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>'
)
_APP_BLANK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"/>'
)
_CUSTOM_BLANK = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"/>'
)
_BLANKS = {"docprops/core.xml": _CORE_BLANK, "docprops/app.xml": _APP_BLANK, "docprops/custom.xml": _CUSTOM_BLANK}

# Parties entièrement supprimées : reconnues par leur nom ou par le type de relation qui les désigne.
_DROP_NAMES = re.compile(
    r"^(?:word/(?:glossary/)?(?:comments[^/]*|people)\.xml"
    r"|xl/comments[^/]*\.xml|xl/(?:comments|threadedcomments|persons|revisions)/.*"
    r"|ppt/comments/.*|ppt/(?:commentauthors|authors)\.xml|ppt/changesinfos/.*"
    r"|docprops/thumbnail\.[a-z0-9]+)$"
)
_DROP_REL_TYPES = {"comments", "commentsextended", "commentsids", "commentsextensible", "people", "threadedcomment",
                   "person", "commentauthors", "authors", "revisionheaders", "revisionlog", "usernames",
                   "changesinfo", "thumbnail"}
# Relations qu'on retire d'une partie quand le contenu qui les utilisait a été supprimé.
_PRUNABLE_REL_TYPES = {"image", "hyperlink", "oleobject", "package", "chart"}

_W_NS = {"http://schemas.openxmlformats.org/wordprocessingml/2006/main",
         "http://purl.oclc.org/ooxml/wordprocessingml/main"}
_W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
# Éléments supprimés avec leur contenu quand on accepte les modifications.
_REVISION_REMOVE = {"del", "movefrom", "rprchange", "pprchange", "sectprchange", "tblprchange", "tblprexchange",
                    "trprchange", "tcprchange", "tblgridchange", "numberingchange", "cellins", "celldel", "cellmerge"}
_MARKERS_REMOVE = {"deltext", "delinstrtext", "commentrangestart", "commentrangeend", "commentreference",
                   "movefromrangestart", "movefromrangeend", "movetorangestart", "movetorangeend",
                   "customxmlinsrangestart", "customxmlinsrangeend", "customxmldelrangestart",
                   "customxmldelrangeend", "customxmlmovefromrangestart", "customxmlmovefromrangeend",
                   "customxmlmovetorangestart", "customxmlmovetorangeend"}
_UNWRAP = {"ins", "moveto"}
_WORD_NEEDS_WORK = re.compile(
    rb"<[A-Za-z0-9]+:(?:ins|del|moveFrom|moveTo|\w+Change|cellIns|cellDel|cellMerge|comment\w*|moveFromRange\w+"
    rb"|moveToRange\w+|customXml\w*Range\w+|delText|delInstrText|conflictIns|conflictDel)[\s/>]"
    rb"|:(?:author|initials)=")
_MAX_NESTING = 3


# ---------------------------------------------------------------- XML (préfixes d'origine conservés)
def _parse(name: str, raw: bytes):
    if b"<!DOCTYPE" in raw or "<!DOCTYPE".encode("utf-16-le") in raw:
        raise CleanError(f"Fichier Office suspect (définition DTD interdite) : {name}")
    try:
        return minidom.parseString(raw)
    except Exception as e:
        raise CleanError(f"Fichier Office illisible ({name}) : {e}")


def _escape(text: str, attribute: bool = False) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")
    if attribute:
        text = text.replace('"', "&quot;").replace("\n", "&#10;").replace("\t", "&#9;")
    return text


def _serialize(doc) -> bytes:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n']
    stack = list(reversed(doc.childNodes))
    while stack:
        node = stack.pop()
        if isinstance(node, str):
            out.append(node)
        elif node.nodeType == Node.ELEMENT_NODE:
            attrs = "".join(f' {k}="{_escape(v, True)}"' for k, v in node.attributes.items())
            if node.childNodes:
                out.append(f"<{node.tagName}{attrs}>")
                stack.append(f"</{node.tagName}>")
                stack.extend(reversed(node.childNodes))
            else:
                out.append(f"<{node.tagName}{attrs}/>")
        elif node.nodeType == Node.TEXT_NODE:
            out.append(_escape(node.data))
        elif node.nodeType == Node.CDATA_SECTION_NODE:
            out.append(f"<![CDATA[{node.data}]]>")
        elif node.nodeType == Node.COMMENT_NODE:
            out.append(f"<!--{node.data}-->")
        elif node.nodeType == Node.PROCESSING_INSTRUCTION_NODE:
            out.append(f"<?{node.target} {node.data}?>")
    return "".join(out).encode("utf-8")


def _elements(root) -> list:
    """Tous les éléments sous `root`, dans l'ordre du document."""
    found, stack = [], [root]
    while stack:
        node = stack.pop()
        if node.nodeType == Node.ELEMENT_NODE:
            found.append(node)
        stack.extend(reversed(node.childNodes))
    return found


def _kids(node) -> list:
    return [c for c in node.childNodes if c.nodeType == Node.ELEMENT_NODE]


def _name(node) -> str:
    return (node.localName or node.tagName).lower()


def _is_w(node, *names) -> bool:
    return node is not None and node.nodeType == Node.ELEMENT_NODE and node.namespaceURI in _W_NS \
        and _name(node) in names


def _child(node, name):
    return next((c for c in _kids(node) if _is_w(c, name)), None)


def _attached(node) -> bool:
    while node.parentNode is not None:
        node = node.parentNode
    return node.nodeType == Node.DOCUMENT_NODE


def _detach(node) -> None:
    if node.parentNode is not None:
        node.parentNode.removeChild(node)


# ---------------------------------------------------------------- Word : accepter les modifications
def _merge_paragraphs(parent, doomed: set) -> None:
    """Saut de paragraphe supprimé : le contenu rejoint le paragraphe suivant (en un seul passage)."""
    has_other = any(_is_w(c, "p") and id(c) not in doomed for c in _kids(parent))
    children, pending, last = [], [], None

    def adopt(target, nodes, anchor_index):
        for node in nodes:
            node.parentNode = target
        target.childNodes[anchor_index:anchor_index] = nodes

    def close_chain():
        """Aucun paragraphe ne suit immédiatement : on garde le dernier s'il porte encore quelque chose."""
        if pending or not (has_other or any(_is_w(c, "p") for c in children)):
            ppr = _child(last, "ppr")
            last.childNodes[:] = [ppr] if ppr is not None else []
            adopt(last, pending, len(last.childNodes))
            children.append(last)
        else:
            last.parentNode = None

    for child in list(parent.childNodes):
        if id(child) in doomed:
            ppr = _child(child, "ppr")
            if ppr is None or _child(ppr, "sectpr") is None:
                if last is not None:
                    last.parentNode = None
                pending.extend(c for c in _kids(child) if not _is_w(c, "ppr"))
                last = child
                continue
        if last is not None and child.nodeType == Node.ELEMENT_NODE:
            if _is_w(child, "p"):
                start = next((i for i, c in enumerate(child.childNodes)
                              if c.nodeType == Node.ELEMENT_NODE and not _is_w(c, "ppr")), len(child.childNodes))
                adopt(child, pending, start)
                last.parentNode = None
            else:
                close_chain()
            pending, last = [], None
        children.append(child)
    if last is not None:
        close_chain()
    parent.childNodes[:] = children


def _accept_word(doc) -> int:
    """Accepte le suivi des modifications et retire les repères de commentaires. Renvoie le nombre de révisions."""
    nodes = _elements(doc.documentElement)
    deleted_marks, deleted_rows, deleted_cells = [], [], []
    for node in nodes:
        if _is_w(node, "p"):
            ppr = _child(node, "ppr")
            rpr = _child(ppr, "rpr") if ppr is not None else None
            if rpr is not None and any(_is_w(c, "del", "movefrom") for c in _kids(rpr)):
                deleted_marks.append(node)
        elif _is_w(node, "tr"):
            trpr = _child(node, "trpr")
            if trpr is not None and _child(trpr, "del") is not None:
                deleted_rows.append(node)
        elif _is_w(node, "tc"):
            tcpr = _child(node, "tcpr")
            if tcpr is not None and _child(tcpr, "celldel") is not None:
                deleted_cells.append(node)

    revisions = 0
    for node in nodes:
        if not _attached(node):
            continue
        conflict = node.namespaceURI == _W14_NS and _name(node) in ("conflictins", "conflictdel")
        if _is_w(node, *_REVISION_REMOVE) or (conflict and _name(node) == "conflictdel"):
            revisions += 1
            _detach(node)
        elif _is_w(node, *_MARKERS_REMOVE):
            parent = node.parentNode
            _detach(node)
            if _is_w(parent, "r") and all(_is_w(c, "rpr") for c in _kids(parent)):
                _detach(parent)
        elif _is_w(node, *_UNWRAP) or conflict:
            revisions += 1
            parent = node.parentNode
            for c in list(node.childNodes):
                parent.insertBefore(c, node)
            parent.removeChild(node)

    for cell in deleted_cells:
        row = cell.parentNode
        _detach(cell)
        if _is_w(row, "tr") and _child(row, "tc") is None:
            deleted_rows.append(row)
    emptied = {}
    for row in deleted_rows:
        table = row.parentNode
        _detach(row)
        if _is_w(table, "tbl"):
            emptied[id(table)] = table
    for table in emptied.values():  # une seule vérification par tableau
        if _attached(table) and not any(_is_w(e, "tr") for e in _elements(table)):
            _detach(table)

    parents = {id(p.parentNode): p.parentNode for p in deleted_marks if _attached(p)}
    doomed = {id(p) for p in deleted_marks}
    for parent in parents.values():
        _merge_paragraphs(parent, doomed)

    for cell in _elements(doc.documentElement):  # une cellule doit se terminer par un paragraphe
        if _is_w(cell, "tc"):
            blocks = [c for c in _kids(cell) if not _is_w(c, "tcpr")]
            if not blocks or _is_w(blocks[-1], "tbl"):
                prefix = cell.prefix + ":" if cell.prefix else ""
                cell.appendChild(doc.createElementNS(cell.namespaceURI, prefix + "p"))

    for node in _elements(doc.documentElement):  # filet de sécurité : aucun nom d'auteur restant
        for i in range(node.attributes.length):
            attr = node.attributes.item(i)
            if (attr.localName or attr.name).lower() in ("author", "initials"):
                attr.value = ""
    return revisions


def _drop_comment_links(doc) -> bool:
    """PowerPoint : retire des diapos les renvois vers les commentaires supprimés."""
    changed = False
    for node in _elements(doc.documentElement):
        if _name(node) == "commentrel" and _attached(node):
            ext = node.parentNode
            while ext is not None and ext.nodeType == Node.ELEMENT_NODE and _name(ext) != "ext":
                ext = ext.parentNode
            if ext is None or ext.nodeType != Node.ELEMENT_NODE:
                continue
            ext_list = ext.parentNode
            _detach(ext)
            if _name(ext_list) == "extlst" and not _kids(ext_list):
                _detach(ext_list)
            changed = True
    return changed


def _author_names(doc) -> list:
    names = []
    for node in _elements(doc.documentElement):
        for i in range(node.attributes.length):
            attr = node.attributes.item(i)
            local = (attr.localName or attr.name).lower()
            if local in ("author", "displayname", "username") or \
                    (local == "name" and _name(node) in ("cmauthor", "author")):
                names.append(attr.value)
        if _name(node) == "author" and node.firstChild is not None and node.firstChild.nodeType == Node.TEXT_NODE:
            names.append("".join(c.data for c in node.childNodes if c.nodeType == Node.TEXT_NODE))
    return [n.strip() for n in names if n.strip() and not n.startswith("tc={")]


# ---------------------------------------------------------------- relations du paquet
def _rels_base(rels_name: str) -> str:
    return posixpath.dirname(posixpath.dirname(rels_name))


def _rels_name_of(part: str) -> str:
    return posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")


def _relations(doc, rels_name: str):
    """(élément, type court, cible interne en minuscules ou None)"""
    for node in _elements(doc.documentElement):
        if _name(node) != "relationship":
            continue
        kind = node.getAttribute("Type").rstrip("/").rsplit("/", 1)[-1].lower()
        target = None
        if node.getAttribute("TargetMode").lower() != "external":
            raw = unquote(node.getAttribute("Target"))
            joined = raw[1:] if raw.startswith("/") else posixpath.join(_rels_base(rels_name), raw)
            target = posixpath.normpath(joined).lower()
        yield node, kind, target


# ---------------------------------------------------------------- nettoyage
def _metadata_found(key: str, raw: bytes) -> list:
    text = raw.decode("utf-8", "ignore")
    found = []
    if key == "docprops/core.xml":
        for tag, label in (("dc:creator", "Auteur"), ("cp:lastModifiedBy", "Dernier modificateur"), ("dc:title", "Titre")):
            m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", text)
            if m:
                found.append(f"{label} : {m.group(1)}")
    elif key == "docprops/app.xml":
        m = re.search(r"<Company>([^<]+)</Company>", text)
        if m:
            found.append(f"Societe : {m.group(1)}")
    return found


def clean_ooxml(data: bytes, depth: int = 0):
    """Renvoie (octets nettoyés, liste de ce qui a été retiré, liste d'avertissements)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zin:
            infos = zin.infolist()
            parts = {i.filename: zin.read(i) for i in infos}
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError) as e:
        raise CleanError(f"Fichier Office corrompu ou non reconnu : {e}")

    found, warnings, authors = [], [], []
    by_key = {name.lower(): name for name in parts}
    rels = {name: _parse(name, raw) for name, raw in parts.items() if name.lower().endswith(".rels")}
    dirty_rels = set()

    removed = {k for k in by_key if _DROP_NAMES.match(k)}
    for rels_name, doc in rels.items():
        removed.update(t for _n, kind, t in _relations(doc, rels_name) if kind in _DROP_REL_TYPES and t in by_key)

    comments = {"comment": 0, "threadedcomment": 0, "cm": 0}
    for key in sorted(removed):
        if not key.endswith(".xml"):
            continue
        doc = _parse(by_key[key], parts[by_key[key]])
        authors.extend(_author_names(doc))
        for node in _elements(doc.documentElement):
            if _name(node) in comments:
                comments[_name(node)] += 1
    # Excel enregistre chaque commentaire « moderne » en double : on ne le compte qu'une fois.
    n_comments = max(comments["comment"], comments["threadedcomment"]) + comments["cm"]

    candidates = set()  # parties qui ne servent peut-être plus à rien

    def drop_part(key: str) -> None:
        removed.add(key)
        rels_key = _rels_name_of(key)
        real = by_key.get(rels_key)
        if real:
            candidates.update(t for _n, _k, t in _relations(rels[real], real) if t)
            removed.add(rels_key)

    for key in list(removed):
        drop_part(key)

    revisions = 0
    for name in list(parts):
        key = name.lower()
        if key in removed or not key.endswith(".xml"):
            continue
        raw = parts[name]
        if key in _BLANKS:
            found.extend(_metadata_found(key, raw))
            parts[name] = _BLANKS[key].encode("utf-8")
        elif key.startswith("word/") and _WORD_NEEDS_WORK.search(raw):
            doc = _parse(name, raw)
            authors.extend(_author_names(doc))
            revisions += _accept_word(doc)
            parts[name] = _serialize(doc)
            real = by_key.get(_rels_name_of(key))
            if real:
                used = {n.attributes.item(i).value for n in _elements(doc.documentElement)
                        for i in range(n.attributes.length)}
                for node, kind, target in list(_relations(rels[real], real)):
                    if kind in _PRUNABLE_REL_TYPES and node.getAttribute("Id") not in used:
                        _detach(node)
                        dirty_rels.add(real)
                        if target:
                            candidates.add(target)
        elif key.startswith("ppt/") and b"commentRel" in raw:
            doc = _parse(name, raw)
            if _drop_comment_links(doc):
                parts[name] = _serialize(doc)

    # Relations pointant vers une partie supprimée.
    for rels_name, doc in rels.items():
        for node, _kind, target in list(_relations(doc, rels_name)):
            if target in removed:
                _detach(node)
                dirty_rels.add(rels_name)

    # Images, liens… qui n'appartenaient qu'au contenu supprimé.
    while candidates:
        key = candidates.pop()
        if key in removed or key not in by_key:
            continue
        still_used = any(t == key for rn, doc in rels.items() if rn.lower() not in removed
                         for _n, _k, t in _relations(doc, rn))
        if not still_used:
            drop_part(key)

    if any(k.startswith("xl/") and "comment" in k for k in removed):
        note = re.compile(rb"<v:shape\b.*?</v:shape>", re.S)
        for name, raw in parts.items():
            if name.lower().endswith(".vml"):
                parts[name] = note.sub(lambda m: b"" if b'ObjectType="Note"' in m.group(0) else m.group(0), raw)

    for rels_name in dirty_rels:
        parts[rels_name] = _serialize(rels[rels_name])

    types_name = by_key.get("[content_types].xml")
    if types_name and removed:
        doc = _parse(types_name, parts[types_name])
        for node in _elements(doc.documentElement):
            if _name(node) == "override" and node.getAttribute("PartName").lstrip("/").lower() in removed:
                _detach(node)
        parts[types_name] = _serialize(doc)

    # Images internes, documents intégrés.
    images, gps, opaque, unhandled = 0, False, 0, set()
    for name in list(parts):
        key = name.lower()
        if key in removed or key.endswith("/"):
            continue
        raw = parts[name]
        ext = posixpath.splitext(key)[1]
        if image_meta.kind_of(raw):
            had_gps = image_meta.has_gps(raw)
            try:
                clean = image_meta.strip(raw)
            except Exception:
                warnings.append(f"ATTENTION : image interne non nettoyée : {name}")
                continue
            if clean != raw:
                parts[name] = clean
                images += 1
                gps = gps or had_gps
        elif "/media/" in key and ext in (".svg", ".gif", ".wdp", ".heic", ".heif"):
            unhandled.add(ext[1:].upper())
        elif "/embeddings/" in key:
            if ext in (".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm") and depth < _MAX_NESTING:
                clean, sub_found, sub_warnings = clean_ooxml(raw, depth + 1)
                parts[name] = clean
                found.extend(f"Document intégré - {f}" for f in sub_found)
                warnings.extend(sub_warnings)
            else:
                opaque += 1

    if revisions:
        found.append(f"Suivi des modifications accepté, texte supprimé retiré ({revisions} révision(s))")
    if n_comments:
        found.append(f"Commentaires supprimés ({n_comments})")
    unique = list(dict.fromkeys(authors))
    if unique:
        found.append("Noms d'auteurs retirés : " + ", ".join(unique[:10]) + ("…" if len(unique) > 10 else ""))
    if any(k.startswith(("xl/revisions/", "ppt/changesinfos/")) for k in removed):
        found.append("Historique des modifications supprimé")
    if any(k.startswith("docprops/thumbnail.") for k in removed):
        found.append("Vignette d'aperçu supprimée")
    if images:
        found.append(f"Images internes nettoyées ({images})")
    if gps:
        found.append("Coordonnees GPS (images internes)")
    if opaque:
        warnings.append(f"ATTENTION : {opaque} objet(s) intégré(s) non nettoyé(s), vérifiez-les")
    if unhandled:
        warnings.append("ATTENTION : images internes non nettoyées, format : " + ", ".join(sorted(unhandled)))

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        written = set()
        for info in infos:
            if info.filename.lower() in removed or info.filename in written:
                continue
            written.add(info.filename)
            zout.writestr(info, parts[info.filename])
    return out.getvalue(), found, warnings
