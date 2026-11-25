"""Nettoyeur : auteurs, texte supprimé, images internes, vignette et fichiers à plusieurs pages."""
import io
import posixpath
import time
import zipfile
from xml.dom import minidom

import pytest
from PIL import Image, ImageSequence

from bouclier import cleaner, image_meta

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
SECRET_AUTHOR = "Jeanne Secretin"


def photo(fmt="JPEG", orientation=None, color="red") -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "CamCorp"
    exif[0x8825] = {1: "N", 2: (48.0, 51.0, 29.0)}
    if orientation:
        exif[0x0112] = orientation
    out = io.BytesIO()
    Image.new("RGB", (40, 20), color).save(out, fmt, exif=exif)
    return out.getvalue()


def rels(*items) -> str:
    body = "".join(
        f'<Relationship Id="{i}" Type="{t}" Target="{target}"{" TargetMode=" + chr(34) + "External" + chr(34) if ext else ""}/>'
        for i, t, target, ext in items)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL}">{body}</Relationships>'


def package(parts: dict) -> bytes:
    overrides = "".join(f'<Override PartName="/{n}" ContentType="application/xml"/>'
                        for n in parts if n.endswith(".xml"))
    parts = {"[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="jpeg" ContentType="image/jpeg"/>' + overrides + "</Types>", **parts}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return out.getvalue()


def unpack(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {n: z.read(n) for n in z.namelist()}


def assert_consistent(parts: dict) -> None:
    """XML bien formé, relations et types de contenu ne pointant que vers des parties existantes."""
    names = {n.lower() for n in parts}
    for name, raw in parts.items():
        if name.endswith((".xml", ".rels")):
            doc = minidom.parseString(raw)
            if name.endswith(".rels"):
                base = posixpath.dirname(posixpath.dirname(name))
                for rel in doc.getElementsByTagName("Relationship"):
                    if rel.getAttribute("TargetMode") != "External":
                        t = rel.getAttribute("Target")
                        t = t[1:] if t.startswith("/") else posixpath.normpath(posixpath.join(base, t))
                        assert t.lower() in names, f"{name} -> {t} manquant"
            if name == "[Content_Types].xml":
                for o in doc.getElementsByTagName("Override"):
                    assert o.getAttribute("PartName")[1:].lower() in names, o.getAttribute("PartName")


def everything(parts: dict) -> bytes:
    return b"\n".join(parts.values())


def make_docx() -> bytes:
    a = f'w:author="{SECRET_AUTHOR}" w:date="2026-01-01T10:00:00Z"'
    body = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:r="{R}" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14"><w:body>
<w:p><w:commentRangeStart w:id="0"/><w:r><w:t xml:space="preserve">Texte gardé </w:t></w:r>
<w:del w:id="1" {a}><w:r><w:delText>MOTDEPASSE-SUPPRIME</w:delText></w:r></w:del>
<w:ins w:id="2" {a}><w:r><w:t>texte inséré</w:t></w:r></w:ins><w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:b/></w:rPr><w:commentReference w:id="0"/></w:r></w:p>
<w:p><w:pPr><w:rPr><w:del w:id="3" {a}/></w:rPr></w:pPr><w:r><w:t xml:space="preserve">Début fusionné </w:t></w:r></w:p>
<w:p><w:pPr><w:jc w:val="center"/><w:pPrChange w:id="4" {a}><w:pPr/></w:pPrChange></w:pPr><w:r><w:rPr><w:i/>
<w:rPrChange w:id="5" {a}><w:rPr/></w:rPrChange></w:rPr><w:t>suite</w:t></w:r></w:p>
<w:p><w:moveFrom w:id="6" {a}><w:r><w:t>ANCIENNE-PLACE</w:t></w:r></w:moveFrom><w:moveTo w:id="7" {a}><w:r><w:t>nouvelle place</w:t></w:r></w:moveTo></w:p>
<w:p><w:del w:id="8" {a}><w:hyperlink r:id="rIdLien"><w:r><w:delText>ancien contact</w:delText></w:r></w:hyperlink>
<w:r><w:drawing r:embed="rIdAncienne"/></w:r></w:del><w:r><w:drawing r:embed="rIdPhoto"/></w:r></w:p>
<w:tbl><w:tblPr/><w:tr><w:trPr><w:del w:id="9" {a}/></w:trPr><w:tc><w:p><w:del w:id="10" {a}><w:r><w:delText>LIGNE-SUPPRIMEE</w:delText></w:r></w:del></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>ligne gardée</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
<w:sectPr/></w:body></w:document>'''
    comments = (f'<w:comments xmlns:w="{W}"><w:comment w:id="0" {a} w:initials="JS"><w:p><w:r><w:t>REMARQUE-PRIVEE'
                '</w:t></w:r></w:p></w:comment></w:comments>')
    people = (f'<w15:people xmlns:w15="http://schemas.microsoft.com/office/word/2012/wordml"><w15:person '
              f'w15:author="{SECRET_AUTHOR}"><w15:presenceInfo w15:providerId="AD" w15:userId="S::jeanne@secret.fr"/>'
              '</w15:person></w15:people>')
    o = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    return package({
        "_rels/.rels": rels(("rId1", o + "officeDocument", "word/document.xml", False),
                            ("rId2", REL + "/metadata/thumbnail", "docProps/thumbnail.jpeg", False),
                            ("rId3", REL + "/metadata/core-properties", "docProps/core.xml", False)),
        "docProps/core.xml": '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                             f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>{SECRET_AUTHOR}</dc:creator></cp:coreProperties>',
        "docProps/thumbnail.jpeg": photo(),
        "word/document.xml": body,
        "word/comments.xml": comments,
        "word/people.xml": people,
        "word/_rels/document.xml.rels": rels(
            ("rIdC", o + "comments", "comments.xml", False),
            ("rIdP", "http://schemas.microsoft.com/office/2011/relationships/people", "people.xml", False),
            ("rIdLien", o + "hyperlink", "mailto:ancien@secret.fr", True),
            ("rIdAncienne", o + "image", "media/ancienne.jpeg", False),
            ("rIdPhoto", o + "image", "media/photo.jpeg", False)),
        "word/media/ancienne.jpeg": photo(color="blue"),
        "word/media/photo.jpeg": photo(orientation=6),
    })


def test_docx_loses_authors_deleted_text_comments_thumbnail_and_exif():
    res = cleaner.clean_file("doc.docx", make_docx())
    parts = unpack(res["data"])
    assert_consistent(parts)
    blob = everything(parts)
    for secret in (SECRET_AUTHOR, "MOTDEPASSE-SUPPRIME", "ANCIENNE-PLACE", "LIGNE-SUPPRIMEE", "REMARQUE-PRIVEE",
                   "jeanne@secret.fr", "ancien@secret.fr", "CamCorp"):
        assert secret.encode() not in blob, secret
    for gone in ("word/comments.xml", "word/people.xml", "docProps/thumbnail.jpeg", "word/media/ancienne.jpeg"):
        assert gone not in parts
    doc = parts["word/document.xml"].decode("utf-8")
    for kept in ("Texte gardé", "texte inséré", "Début fusionné", "suite", "nouvelle place", "ligne gardée",
                 'mc:Ignorable="w14"', "xmlns:w14=", "<w:i/>", "<w:b") :
        assert kept in doc or kept == "<w:b", kept
    for marker in ("<w:del ", "<w:ins ", "commentR", "pPrChange", "rPrChange", "delText", "moveFrom", "moveTo"):
        assert marker not in doc, marker
    tree = minidom.parseString(parts["word/document.xml"])
    merged = [p for p in tree.getElementsByTagName("w:p")
              if "Début fusionné" in p.toxml() and "suite" in p.toxml()]
    assert merged, "le paragraphe dont le saut a été supprimé doit fusionner avec le suivant"
    assert len(tree.getElementsByTagName("w:tr")) == 1
    image = Image.open(io.BytesIO(parts["word/media/photo.jpeg"]))
    assert dict(image.getexif()) == {0x0112: 6}  # seule l'orientation reste
    report = " | ".join(res["found"])
    for expected in (SECRET_AUTHOR, "Commentaires supprimés (1)", "Suivi des modifications", "Vignette",
                     "Images internes nettoyées", "GPS"):
        assert expected in report, expected
    assert res["warnings"] == []


def test_xlsx_comments_persons_and_history_are_removed():
    o = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    s = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    vml = ('<xml xmlns:v="urn:schemas-microsoft-com:vml" xmlns:x="urn:schemas-microsoft-com:office:excel">'
           '<v:shapetype id="t"></v:shapetype><v:shape id="a"><x:ClientData ObjectType="Note"/></v:shape>'
           '<v:shape id="b"><x:ClientData ObjectType="Button"/></v:shape></xml>')
    data = package({
        "_rels/.rels": rels(("rId1", o + "officeDocument", "xl/workbook.xml", False)),
        "xl/workbook.xml": f'<workbook xmlns="{s}"/>',
        "xl/_rels/workbook.xml.rels": rels(
            ("rId1", o + "worksheet", "worksheets/sheet1.xml", False),
            ("rId2", "http://schemas.microsoft.com/office/2017/10/relationships/person", "persons/person.xml", False),
            ("rId3", o + "revisionHeaders", "revisions/revisionHeaders.xml", False)),
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{s}"><sheetData/></worksheet>',
        "xl/worksheets/_rels/sheet1.xml.rels": rels(
            ("rId1", o + "comments", "../comments/comment1.xml", False),
            ("rId2", o + "vmlDrawing", "../drawings/vmlDrawing1.vml", False),
            ("rId3", "http://schemas.microsoft.com/office/2017/10/relationships/threadedComment",
             "../threadedComments/threadedComment1.xml", False)),
        "xl/comments/comment1.xml": f'<comments xmlns="{s}"><authors><author>{SECRET_AUTHOR}</author></authors>'
                                    '<commentList><comment ref="A1"><text><t>REMARQUE-PRIVEE</t></text></comment></commentList></comments>',
        "xl/threadedComments/threadedComment1.xml": '<ThreadedComments><threadedComment ref="A1"><text>REMARQUE-PRIVEE</text></threadedComment></ThreadedComments>',
        "xl/persons/person.xml": f'<personList><person displayName="{SECRET_AUTHOR}" id="1"/></personList>',
        "xl/revisions/revisionHeaders.xml": f'<headers><header userName="{SECRET_AUTHOR}"/></headers>',
        "xl/revisions/_rels/revisionHeaders.xml.rels": rels(("rId1", o + "revisionLog", "revisionLog1.xml", False)),
        "xl/revisions/revisionLog1.xml": "<revisions><v>ANCIENNE-VALEUR</v></revisions>",
        "xl/drawings/vmlDrawing1.vml": vml,
    })
    res = cleaner.clean_file("t.xlsx", data)
    parts = unpack(res["data"])
    assert_consistent(parts)
    blob = everything(parts)
    for secret in (SECRET_AUTHOR, "REMARQUE-PRIVEE", "ANCIENNE-VALEUR"):
        assert secret.encode() not in blob, secret
    kept_vml = parts["xl/drawings/vmlDrawing1.vml"]
    assert b'ObjectType="Note"' not in kept_vml and b'ObjectType="Button"' in kept_vml and b"shapetype" in kept_vml
    assert "Commentaires supprimés (1)" in res["found"] and SECRET_AUTHOR in " ".join(res["found"])


def test_pptx_legacy_and_modern_comments_are_removed():
    o = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    modern = "http://schemas.microsoft.com/office/2018/10/relationships/"
    slide = (f'<p:sld xmlns:p="{p}" xmlns:r="{R}" xmlns:p188="http://schemas.microsoft.com/office/powerpoint/2018/8/main">'
             '<p:cSld/><p:extLst><p:ext uri="{6950BFC3}"><p188:commentRel r:id="rId2"/></p:ext></p:extLst></p:sld>')
    data = package({
        "_rels/.rels": rels(("rId1", o + "officeDocument", "ppt/presentation.xml", False)),
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{p}"/>',
        "ppt/_rels/presentation.xml.rels": rels(
            ("rId1", o + "slide", "slides/slide1.xml", False),
            ("rId2", o + "commentAuthors", "commentAuthors.xml", False),
            ("rId3", modern + "authors", "authors.xml", False)),
        "ppt/slides/slide1.xml": slide,
        "ppt/slides/_rels/slide1.xml.rels": rels(
            ("rId1", o + "comments", "../comments/comment1.xml", False),
            ("rId2", modern + "comments", "../comments/modernComment_1.xml", False)),
        "ppt/commentAuthors.xml": f'<p:cmAuthorLst xmlns:p="{p}"><p:cmAuthor id="0" name="{SECRET_AUTHOR}" initials="JS"/></p:cmAuthorLst>',
        "ppt/authors.xml": f'<authorLst><author id="1" name="{SECRET_AUTHOR}"/></authorLst>',
        "ppt/comments/comment1.xml": f'<p:cmLst xmlns:p="{p}"><p:cm><p:text>REMARQUE-PRIVEE</p:text></p:cm></p:cmLst>',
        "ppt/comments/modernComment_1.xml": "<cmLst><cm><t>REMARQUE-PRIVEE</t></cm></cmLst>",
    })
    res = cleaner.clean_file("t.pptx", data)
    parts = unpack(res["data"])
    assert_consistent(parts)
    blob = everything(parts)
    assert SECRET_AUTHOR.encode() not in blob and b"REMARQUE-PRIVEE" not in blob
    assert b"commentRel" not in parts["ppt/slides/slide1.xml"] and b"extLst" not in parts["ppt/slides/slide1.xml"]


def test_embedded_documents_are_cleaned_and_opaque_objects_reported():
    data = package({"word/document.xml": f'<w:document xmlns:w="{W}"><w:body/></w:document>',
                    "word/embeddings/classeur.docx": make_docx(), "word/embeddings/oleObject1.bin": b"\xd0\xcf\x11\xe0"})
    res = cleaner.clean_file("d.docx", data)
    inner = unpack(unpack(res["data"])["word/embeddings/classeur.docx"])
    assert SECRET_AUTHOR.encode() not in everything(inner)
    assert any("non nettoyé" in w for w in res["warnings"])


def test_dtd_is_refused():
    data = package({"word/document.xml": f'<!DOCTYPE x [<!ENTITY a "b">]><w:document xmlns:w="{W}"><w:ins/></w:document>'})
    with pytest.raises(cleaner.CleanError):
        cleaner.clean_file("d.docx", data)


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_lossless_strip_removes_metadata_and_keeps_pixels(fmt):
    original = photo(fmt)
    clean = image_meta.strip(original + b"DONNEES-AJOUTEES-APRES")
    before, after = Image.open(io.BytesIO(original)), Image.open(io.BytesIO(clean))
    assert len(after.getexif()) == 0 and b"CamCorp" not in clean and b"DONNEES-AJOUTEES" not in clean
    assert before.convert("RGB").tobytes() == after.convert("RGB").tobytes()


@pytest.mark.parametrize("ext,fmt", [(".tif", "TIFF"), (".webp", "WEBP"), (".png", "PNG")])
def test_every_page_or_frame_is_kept(ext, fmt):
    frames = [Image.new("RGB", (30, 30), c) for c in ("red", "green", "blue")]
    exif = Image.Exif()
    exif[0x010F] = "CamCorp"
    out = io.BytesIO()
    extra = {} if fmt == "TIFF" else {"duration": [100, 200, 300], "loop": 0}
    if fmt == "WEBP":
        extra["lossless"] = True
    frames[0].save(out, fmt, save_all=True, append_images=frames[1:], exif=exif, **extra)
    res = cleaner.clean_file("anim" + ext, out.getvalue())
    img = Image.open(io.BytesIO(res["data"]))
    assert img.n_frames == 3 and b"CamCorp" not in res["data"]
    colors = [f.convert("RGB").getpixel((5, 5)) for f in ImageSequence.Iterator(img)]
    assert colors == [(255, 0, 0), (0, 128, 0), (0, 0, 255)]
    assert res["found"]


def test_many_deleted_paragraph_breaks_are_merged_quickly():
    mark = '<w:pPr><w:rPr><w:del w:id="1" w:author="x"/></w:rPr></w:pPr>'
    body = "".join(f"<w:p>{mark}<w:r><w:t>m{i} </w:t></w:r></w:p>" for i in range(5000)) + "<w:p/>"
    data = package({"word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'})
    start = time.perf_counter()
    out = unpack(cleaner.clean_file("long.docx", data)["data"])["word/document.xml"]
    assert time.perf_counter() - start < 20
    assert out.count(b"<w:p>") == 1 and out.count(b"<w:t>") == 5000 and out.find(b"m0 ") < out.find(b"m4999 ")


def test_deleted_break_before_a_table_keeps_the_text():
    mark = '<w:pPr><w:rPr><w:del w:id="1" w:author="x"/></w:rPr></w:pPr>'
    body = (f"<w:p>{mark}<w:r><w:t>premier</w:t></w:r></w:p><w:p>{mark}<w:r><w:t>second</w:t></w:r></w:p>"
            f"<w:tbl><w:tr><w:tc><w:p>{mark}</w:p></w:tc></w:tr></w:tbl><w:p>{mark}</w:p><w:p><w:r><w:t>fin</w:t></w:r></w:p>")
    data = package({"word/document.xml": f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'})
    tree = minidom.parseString(unpack(cleaner.clean_file("t.docx", data)["data"])["word/document.xml"])
    top = [c for c in tree.getElementsByTagName("w:body")[0].childNodes if c.nodeType == c.ELEMENT_NODE]
    assert [c.tagName for c in top] == ["w:p", "w:tbl", "w:p"]
    assert "premier" in top[0].toxml() and "second" in top[0].toxml() and "fin" in top[2].toxml()
    assert len(top[1].getElementsByTagName("w:p")) == 1  # une cellule garde toujours un paragraphe
