# PyInstaller : construit le dossier dist\Bouclier (exécutable sans console, sans Python requis chez l'utilisateur)
from PyInstaller.utils.hooks import collect_data_files
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [
    (os.path.join(ROOT, "bouclier", "ui", "qml"), "bouclier/ui/qml"),
    (os.path.join(ROOT, "bouclier", "ui", "assets"), "bouclier/ui/assets"),
    (os.path.join(ROOT, "bouclier", "ui", "translations_extra.json"), "bouclier/ui"),
]
datas += collect_data_files("cv2", includes=["data/*.xml"])  # détecteur de visages (Haar)
datas += collect_data_files("PySide6", includes=["Qt/qml/QtQuick/*", "Qt/qml/QtQuick/**/*", "Qt/qml/QtQml/**/*", "Qt/qml/QtCore/**/*"])
a = Analysis([os.path.join(ROOT, "Bouclier.pyw")], pathex=[ROOT], datas=datas,
             hiddenimports=["PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickControls2", "PySide6.QtWidgets", "PySide6.QtSvg",
                            "cv2", "pytesseract", "pypdf", "PIL"],
             excludes=["tkinter", "pytest", "matplotlib", "scipy", "pandas", "IPython", "PyQt5", "PyQt6", "PySide2",
                       # modules Qt que Bouclier n'utilise pas (il utilise Core, Gui, Widgets, Qml, Quick, Svg)
                       "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
                       "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
                       "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
                       "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtQuick3D", "PySide6.QtCharts",
                       "PySide6.QtDataVisualization", "PySide6.QtGraphs", "PySide6.QtMultimedia",
                       "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
                       "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
                       "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors", "PySide6.QtSerialPort",
                       "PySide6.QtSerialBus", "PySide6.QtLocation", "PySide6.QtPositioning",
                       "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
                       "PySide6.QtHttpServer", "PySide6.QtNetworkAuth", "PySide6.QtVirtualKeyboard",
                       "PySide6.QtQuickTest", "PySide6.QtUiTools"])

# Retire du paquet les bibliothèques, plugins et ressources Qt inutilisés (allège fortement dist\Bouclier).
_UNUSED = (
    "qt6webengine", "qtwebengine", "qt6webchannel", "qt6websockets", "qt6pdf", "qtpdf",
    "qt63d", "qt3d", "qt6quick3d", "quick3d", "qt6charts", "qtcharts", "qt6datavisualization",
    "qt6graphs", "qt6multimedia", "qtmultimedia", "qt6spatialaudio", "qt6texttospeech",
    "qt6sql", "qt6test", "qt6designer", "qt6help", "qt6bluetooth", "qt6nfc", "qt6sensors",
    "qt6serialport", "qt6serialbus", "qt6location", "qt6positioning", "qt6remoteobjects",
    "qt6scxml", "qt6statemachine", "qt6httpserver", "qt6networkauth", "qt6virtualkeyboard",
    "qt6quicktest", "qt6uitools",
    "/plugins/multimedia/", "/plugins/sqldrivers/", "/plugins/designer/", "/plugins/position/",
    "/plugins/sensors/", "/plugins/geoservices/", "/plugins/virtualkeyboard/", "/plugins/canbus/",
    "/plugins/scxmldatamodel/", "/plugins/renderers/", "/plugins/sceneparsers/",
    "/plugins/geometryloaders/", "/plugins/renderplugins/", "/plugins/texttospeech/",
    "/qtquick/virtualkeyboard/", "/qtquick/scene3d/", "/qtquick/scene2d/",
    # OpenCV : lecture/écriture vidéo (ffmpeg, ~29 Mo) inutile, Bouclier ne traite que des images
    "opencv_videoio_ffmpeg",
    # Pillow : format AVIF (~7 Mo), Bouclier gère JPEG, PNG, WEBP, TIFF
    "pil/_avif",
    # Styles Qt Quick Controls autres que « Basic » (le seul utilisé par l'appli)
    "qt6quickcontrols2fluentwinui3", "qt6quickcontrols2fusion", "qt6quickcontrols2imagine",
    "qt6quickcontrols2material", "qt6quickcontrols2universal", "qt6quickcontrols2windows",
    "qt6quickcontrols2macos", "qt6quickcontrols2ios",
    "/qtquick/controls/fluentwinui3/", "/qtquick/controls/fusion/", "/qtquick/controls/imagine/",
    "/qtquick/controls/material/", "/qtquick/controls/universal/", "/qtquick/controls/windows/",
    "/qtquick/controls/macos/", "/qtquick/controls/ios/",
)


def _keep(entry):
    name = str(entry[0]).replace("\\", "/").lower()
    name = "/" + name if not name.startswith("/") else name
    return not any(bad in name for bad in _UNUSED)


a.binaries = [e for e in a.binaries if _keep(e)]
a.datas = [e for e in a.datas if _keep(e)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Bouclier", console=False,
          icon=os.path.join(SPECPATH, "icone.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="Bouclier")
