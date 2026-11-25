"""Sans OCR (ou si l'OCR échoue), Bouclier ne doit JAMAIS laisser croire que l'image est sûre."""
import io
import time

import pytest
from PIL import Image

from bouclier import ocr_engine
from bouclier.ui import services

REASSURING = "Aucune donnée sensible repérée"
FACE = {"id": -1, "type": "face", "label": "Visage", "value": "Visage détecté", "boxes": [[5, 5, 40, 40]], "excluded": False}


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(out, "PNG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def no_log(monkeypatch):
    monkeypatch.setattr(services, "log_error", lambda text: "")


def set_ocr(monkeypatch, available, error=None, faces=0):
    monkeypatch.setattr(ocr_engine, "has_tesseract", lambda: available)

    def run(_img):
        if error:
            raise ocr_engine.OCRError(error)
        return []

    monkeypatch.setattr(ocr_engine, "run_tesseract_ocr", run)
    monkeypatch.setattr(services, "detect_face_entities",
                        lambda img: [dict(FACE, boxes=[list(FACE["boxes"][0])]) for _ in range(faces)])


def test_missing_tesseract_is_reported_even_with_face_detector(monkeypatch):
    set_ocr(monkeypatch, False)
    found = services.detect_entities(png())
    assert found["entities"] == [] and found["ocr_error"] == services.OCR_UNREAD_MISSING


def test_ocr_failure_is_not_swallowed(monkeypatch):
    set_ocr(monkeypatch, True, error="Tesseract a echoue : langue absente", faces=1)
    found = services.detect_entities(png())
    assert len(found["entities"]) == 1
    assert found["ocr_error"].startswith(services.OCR_FAILED_PREFIX) and "langue absente" in found["ocr_error"]


def test_working_ocr_has_no_warning(monkeypatch):
    set_ocr(monkeypatch, True)
    assert services.detect_entities(png())["ocr_error"] == ""


# ---------------------------------------------------------------- comportement de l'interface
@pytest.fixture
def ui(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from bouclier.ui import backends

    app = QApplication.instance() or QApplication([])
    owner = backends.AppBackend()
    images = backends.ImageBackend(owner)
    toasts = []
    owner.toast.connect(lambda kind, msg: toasts.append((kind, msg)))
    path = tmp_path / "scan.png"
    path.write_bytes(png())

    def wait():
        end = time.time() + 10
        app.processEvents()
        while images.busy and time.time() < end:
            time.sleep(0.01)
            app.processEvents()
        assert not images.busy

    images.openFile(str(path))
    wait()
    toasts.clear()
    return images, toasts, wait


def text_of(toasts):
    return " | ".join(m for _k, m in toasts)


def test_detect_without_ocr_never_reassures(monkeypatch, ui):
    images, toasts, wait = ui
    set_ocr(monkeypatch, False)
    images.detect()
    wait()
    assert REASSURING not in text_of(toasts) and "NON lu" in text_of(toasts)
    assert images.textWarning and all(kind != "success" for kind, _m in toasts)


def test_anonymize_without_ocr_and_nothing_to_mask_produces_no_image(monkeypatch, ui):
    images, toasts, wait = ui
    set_ocr(monkeypatch, False)
    images.anonymize()
    wait()
    assert not images.hasResult
    assert REASSURING not in text_of(toasts) and "NON lu" in text_of(toasts)


def test_anonymize_without_ocr_with_faces_warns(monkeypatch, ui):
    images, toasts, wait = ui
    set_ocr(monkeypatch, False, faces=1)
    images.anonymize()
    wait()
    assert images.hasResult and images.textWarning
    assert "NON lu : seules 1 zone(s)" in text_of(toasts) and all(kind != "success" for kind, _m in toasts)


def test_manual_zone_without_ocr_warns_and_save_warns_again(monkeypatch, ui, tmp_path):
    images, toasts, wait = ui
    set_ocr(monkeypatch, False)
    images.addBox(10, 10, 60, 40)
    images.anonymize()
    wait()
    assert images.hasResult and "NON lu" in text_of(toasts)
    toasts.clear()
    images.saveResult(str(tmp_path / "out.png"))
    assert "n'a pas été lu" in text_of(toasts)


def test_ocr_installed_afterwards_reruns_detection_and_keeps_exclusions(monkeypatch, ui):
    images, toasts, wait = ui
    set_ocr(monkeypatch, False, faces=1)
    images.detect()
    wait()
    images.setEntityExcluded(0, True)
    set_ocr(monkeypatch, True, faces=1)
    images.addBox(100, 10, 150, 40)
    toasts.clear()
    images.anonymize()
    wait()
    assert images.textWarning == "" and images.entities[0]["excluded"]
    assert "NON lu" not in text_of(toasts) and "1 zone(s) masquée(s)" in text_of(toasts)


def test_manual_only_mode_does_not_warn(monkeypatch, ui):
    images, toasts, wait = ui
    set_ocr(monkeypatch, False)
    images.setAutoDetect(False)
    images.addBox(10, 10, 60, 40)
    images.anonymize()
    wait()
    assert images.hasResult and "NON lu" not in text_of(toasts)


def test_multipage_image_is_announced(ui, tmp_path):
    images, toasts, wait = ui
    path = tmp_path / "deux_pages.tif"
    first = Image.new("RGB", (50, 50), "white")
    first.save(path, save_all=True, append_images=[Image.new("RGB", (50, 50), "black")])
    images.openFile(str(path))
    wait()
    assert "2 pages" in images.pageWarning and "2 pages" in text_of(toasts)
