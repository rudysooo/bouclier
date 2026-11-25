import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TranslationCompletenessTests(unittest.TestCase):
    def test_english_dictionary_has_core_workflow_strings(self):
        data = json.loads((ROOT / "bouclier" / "ui" / "translations_extra.json").read_text(encoding="utf-8"))
        en = data["en"]
        for source in ("Enregistrer l'image anonymisée", "Aucune donnée sensible repérée.", "Cliquez sur « Détecter » pour lister les données, puis excluez celles à conserver.", "Nettoyage en cours…", "Langue de l'interface", "Supprimer ce motif ?"):
            self.assertIn(source, en, source)
            self.assertTrue(en[source], source)

    def test_manual_canvas_uses_transformed_image_coordinates(self):
        qml = (ROOT / "bouclier" / "ui" / "qml" / "components" / "ImageCanvas.qml").read_text(encoding="utf-8")
        self.assertIn("area.mapToItem(stage, mx, my)", qml)

if __name__ == "__main__":
    unittest.main()
