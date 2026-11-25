"""Point d'entrée de la nouvelle interface Qt Quick (PySide6)."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _log(text: str) -> None:
    from . import services
    services.log_error(text)


def main(argv=None) -> int:
    argv = list(sys.argv if argv is None else argv)
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")  # style neutre : tout est habillé par notre thème

    from PySide6.QtCore import QUrl, Qt, qInstallMessageHandler
    from PySide6.QtGui import QFont, QFontDatabase, QIcon
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine

    closing = {"on": False}

    def qt_messages(mode, ctx, message):
        """Conserve les diagnostics Qt, même lorsque l'application tourne via pythonw."""
        if closing["on"]:
            return  # destruction de l'interface : les « of null » ici sont attendus et sans effet
        location = f"{ctx.file or '<Qt>'}:{ctx.line or 0}"
        entry = f"[Qt/{mode}] {message} ({location})"
        try:
            _log(entry)
        except Exception:
            # Le gestionnaire Qt ne doit jamais provoquer une seconde erreur.
            pass
        # En mode diagnostic, rendre les erreurs visibles dans la console aussi.
        if mode in (1, 2, 3) and sys.stderr is not None:
            try:
                print(entry, file=sys.stderr, flush=True)
            except Exception:
                pass

    qInstallMessageHandler(qt_messages)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Bouclier")
    app.setOrganizationName("Bouclier")
    app.setWindowIcon(QIcon(str(HERE / "assets" / "logo.svg")))

    # Police Inter embarquée (assets/fonts/*.ttf|otf) ; sinon police système propre.
    family = None
    for f in sorted((HERE / "assets" / "fonts").glob("Inter*")):
        if f.suffix.lower() in (".ttf", ".otf"):
            fid = QFontDatabase.addApplicationFont(str(f))
            if fid >= 0 and family is None:
                family = QFontDatabase.applicationFontFamilies(fid)[0]
    if family is None:
        family = "Segoe UI" if sys.platform.startswith("win") else ".AppleSystemUIFont" if sys.platform == "darwin" else "Noto Sans"
    app.setFont(QFont(family, 10))

    from .backends import AppBackend, CleanerBackend, ImageBackend, PatternsBackend, ScamBackend, TextBackend

    backend = AppBackend()
    backends = {
        "appBackend": backend,
        "imageBackend": ImageBackend(backend),
        "textBackend": TextBackend(backend),
        "cleanerBackend": CleanerBackend(backend),
        "scamBackend": ScamBackend(backend),
        "patternsBackend": PatternsBackend(backend),
    }

    def excepthook(et, ev, tb):
        text = "".join(traceback.format_exception(et, ev, tb))
        _log("Exception non attrapée :\n" + text)
        backend.toast.emit("error", f"Erreur inattendue : {ev} (détail : bouclier_erreur.log)")

    sys.excepthook = excepthook

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(HERE / "qml"))
    for name, obj in backends.items():
        engine.rootContext().setContextProperty(name, obj)
    engine.warnings.connect(lambda ws: None if closing["on"] else [_log("[QML] " + w.toString()) for w in ws])
    engine.load(QUrl.fromLocalFile(str(HERE / "qml" / "Main.qml")))
    if not engine.rootObjects():
        raise RuntimeError("L'interface QML n'a pas pu être chargée (voir bouclier_erreur.log).")

    backend.refreshOcr()
    code = app.exec()
    # Fermeture propre : le moteur QML doit disparaître AVANT les backends Python.
    closing["on"] = True
    engine.deleteLater()
    del engine
    import gc
    gc.collect()
    app.processEvents()
    backends.clear()
    del backend
    return code


if __name__ == "__main__":
    sys.exit(main())
