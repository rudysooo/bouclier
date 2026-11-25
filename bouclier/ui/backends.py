"""Backends exposés à QML (QObject + Signal/Slot/Property).

Règles :
- aucun traitement lourd sur le thread UI : tout passe par `_Base._async` (thread Python + retour
  sur le thread UI via un signal) ;
- toute exception est attrapée, affichée (toast) et, si inattendue, journalisée dans bouclier_erreur.log.
"""
from __future__ import annotations

import atexit
import re
import shutil
import tempfile
import threading
import traceback
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import (Property, QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, Signal, Slot)
from PySide6.QtGui import QGuiApplication

from . import services
from .. import __version__


_DYNAMIC_TR = [
    (r"Seuls les visages ont été recherchés : (\d+) repéré\(s\)\.", {"en": "Only faces were searched for: {0} found.", "es": "Solo se han buscado rostros: {0} detectado(s)."}),
    (r"Texte NON lu : seules (\d+) zone\(s\) \(visages et zones manuelles\) ont été masquées\. Vérifiez l'image avant de la partager\.", {"en": "Text NOT read: only {0} region(s) (faces and manual regions) were redacted. Check the image before sharing.", "es": "Texto NO leído: solo se han ocultado {0} zona(s) (rostros y zonas manuales). Revisa la imagen antes de compartirla."}),
    (r"Ce fichier contient (\d+) pages ou images : seule la première est traitée et enregistrée\.", {"en": "This file has {0} pages or frames: only the first one is processed and saved.", "es": "Este archivo tiene {0} páginas o imágenes: solo se procesa y guarda la primera."}),
    (r"(\d+) fichier\(s\) à vérifier : certains éléments n'ont pas pu être nettoyés\.", {"en": "{0} file(s) to check: some items could not be cleaned.", "es": "{0} archivo(s) por revisar: no se han podido limpiar algunos elementos."}),
    (r"Suivi des modifications accepté, texte supprimé retiré \((\d+) révision\(s\)\)", {"en": "Tracked changes accepted, deleted text removed ({0} revision(s))", "es": "Control de cambios aceptado, texto borrado eliminado ({0} revisión(es))"}),
    (r"Commentaires supprimés \((\d+)\)", {"en": "Comments removed ({0})", "es": "Comentarios eliminados ({0})"}),
    (r"Noms d'auteurs retirés : (.*)", {"en": "Author names removed: {0}", "es": "Nombres de autores eliminados: {0}"}),
    (r"Images internes nettoyées \((\d+)\)", {"en": "Embedded images cleaned ({0})", "es": "Imágenes internas limpiadas ({0})"}),
    (r"ATTENTION : (\d+) objet\(s\) intégré\(s\) non nettoyé\(s\), vérifiez-les", {"en": "WARNING: {0} embedded object(s) not cleaned, check them", "es": "ATENCIÓN: {0} objeto(s) incrustado(s) sin limpiar, revísalos"}),
    (r"ATTENTION : images internes non nettoyées, format : (.*)", {"en": "WARNING: embedded images not cleaned, format: {0}", "es": "ATENCIÓN: imágenes internas sin limpiar, formato: {0}"}),
    (r"ATTENTION : image interne non nettoyée : (.*)", {"en": "WARNING: embedded image not cleaned: {0}", "es": "ATENCIÓN: imagen interna sin limpiar: {0}"}),
    (r"Analyse impossible : (.*)", {"en": "Analysis failed: {0}", "es": "Análisis imposible: {0}"}),
    (r"Enregistrement impossible : (.*)", {"en": "Could not save image: {0}", "es": "No se pudo guardar la imagen: {0}"}),
    (r"Image chargée : (.*)", {"en": "Image loaded: {0}", "es": "Imagen cargada: {0}"}),
    (r"Image enregistrée : (.*)", {"en": "Image saved: {0}", "es": "Imagen guardada: {0}"}),
    (r"Impossible d'ouvrir la fenêtre d'enregistrement : (.*)", {"en": "Could not open the save dialog: {0}", "es": "No se pudo abrir el diálogo para guardar: {0}"}),
    (r"Langue modifiée, mais impossible d'enregistrer le paramètre : (.*)", {"en": "Language changed, but the setting could not be saved: {0}", "es": "Idioma cambiado, pero no se pudo guardar el ajuste: {0}"}),
    (r"Mot-clé « (.*) » ajouté\.", {"en": "Keyword “{0}” added.", "es": "Palabra clave «{0}» añadida."}),
    (r"Motif « (.*) » ajouté\.", {"en": "Pattern “{0}” added.", "es": "Patrón «{0}» añadido."}),
    (r"(\d+) zone\(s\) masquée\(s\)\. Vous pouvez enregistrer l'image\.", {"en": "{0} region(s) redacted. You can save the image.", "es": "{0} zona(s) ocultada(s). Puedes guardar la imagen."}),
    (r"(\d+) fichier\(s\) ignoré\(s\) : format non pris en charge\.", {"en": "{0} file(s) skipped: unsupported format.", "es": "{0} archivo(s) omitido(s): formato no compatible."}),
    (r"(\d+) donnée\(s\) sensible\(s\) repérée\(s\)\.", {"en": "{0} sensitive item(s) found.", "es": "{0} dato(s) sensible(s) detectado(s)."}),
]

class _Base(QObject):
    """Exécute du travail hors du thread UI et renvoie le résultat sur le thread UI."""
    _dispatchSig = Signal(object)

    def __init__(self, app: "Optional[AppBackend]" = None, parent=None):
        super().__init__(parent)
        self._app = app
        self._dispatchSig.connect(self._dispatch)

    @Slot(object)
    def _dispatch(self, fn):
        try:
            fn()
        except Exception:  # un callback d'interface ne doit jamais faire tomber l'appli
            services.log_error("Callback UI :\n" + traceback.format_exc())
            self._notify("error", "Erreur interne de l'interface (détail dans bouclier_erreur.log).")

    def _notify(self, kind: str, message: str) -> None:
        target = self._app if self._app is not None else self
        sig = getattr(target, "toast", None)
        if sig is not None:
            # Tous les messages backend passent par le traducteur courant, y compris les toasts.
            if self._app is not None:
                try:
                    message = self._app.tr(message, self._app.language)
                except Exception:
                    pass
            sig.emit(kind, message)

    def _async(self, work: Callable, ok: Callable, fail: Optional[Callable] = None, with_progress: bool = False) -> None:
        def progress(msg: str) -> None:
            self._dispatchSig.emit(lambda m=msg: self._on_progress(m))

        def runner():
            try:
                res = work(progress) if with_progress else work()
            except BaseException as e:  # noqa: BLE001
                tb = traceback.format_exc()
                self._dispatchSig.emit(lambda e=e, tb=tb: self._failed(e, tb, fail))
            else:
                self._dispatchSig.emit(lambda r=res: ok(r))

        threading.Thread(target=runner, daemon=True).start()

    def _on_progress(self, msg: str) -> None:  # surchargé si besoin
        pass

    def _failed(self, exc: BaseException, tb: str, fail: Optional[Callable]) -> None:
        msg, unexpected = services.format_exception(exc)
        if unexpected:
            services.log_error(tb)
            msg += "  (détail : bouclier_erreur.log)"
        self._notify("error", msg)
        if fail:
            fail(msg)


# =============================================================================== application
class AppBackend(_Base):
    toast = Signal(str, str)           # (kind: success|error|warning|info, message)
    themeChanged = Signal()
    ocrChanged = Signal()

    def __init__(self):
        super().__init__(None)
        self._settings = services.load_settings()
        self._theme = self._settings.get("theme", "dark") if self._settings.get("theme") in ("dark", "light") else "dark"
        self._language = self._settings.get("language", "fr") if self._settings.get("language") in ("fr", "en", "es") else "fr"
        self._ocr_state = "checking"       # checking | ready | error
        self._ocr_message = "Vérification de l'OCR…"
        self._ocr_installing = False
        self._ocr_log = ""

    # -- thème
    def _get_theme(self): return self._theme
    theme = Property(str, _get_theme, notify=themeChanged)

    languageChanged = Signal()
    @Property(str, notify=languageChanged)
    def language(self): return self._language

    @Slot(str)
    def setLanguage(self, value: str) -> None:
        if value in ("fr", "en", "es") and value != self._language:
            self._language = value
            self._settings["language"] = value
            # Emit first so every QML binding updates immediately; persistence errors must not
            # leave the visible interface stuck in the previous language.
            self.languageChanged.emit()
            try:
                services.save_settings(self._settings)
            except Exception as exc:
                self._notify("warning", f"Langue modifiée, mais impossible d'enregistrer le paramètre : {exc}")

    @Slot(str, str, result=str)
    def tr(self, text: str, language: str = "") -> str:
        translations = {
            "en": {
                "Images": "Images", "Texte": "Text", "Nettoyeur de fichiers": "File cleaner", "Anti-arnaque": "Scam checker", "Motifs et mots-clés": "Patterns & keywords", "Paramètres": "Settings",
                "Langue de l'interface": "Interface language", "Français": "French", "Anglais": "English", "Espagnol": "Spanish", "Apparence": "Appearance", "Sombre": "Dark", "Clair": "Light",
                "Le changement est immédiat et mémorisé.": "Changes apply immediately and are saved.", "Choisir une image": "Choose an image", "Déposez une image ici": "Drop an image here", "Anonymiser": "Redact", "Anonymiser à nouveau": "Redact again", "Enregistrer l'image": "Save image", "Traitement…": "Processing…", "Détecter": "Detect", "Données détectées": "Detected data", "Type de masquage": "Redaction style", "Noir": "Black", "Flou": "Blur", "Mosaïque": "Pixelate", "Lecture automatique (OCR)": "Automatic text recognition (OCR)", "Effacer toutes les zones ?": "Clear all regions?", "Effacer": "Clear", "Réglages modifiés : relancez l'anonymisation": "Settings changed: redact again", "Nettoyeur de métadonnées": "Metadata cleaner", "Ajouter des fichiers": "Add files", "Nettoyer": "Clean", "Vider la liste": "Clear list", "Analyser le message": "Analyze message", "En attente d'un message": "Waiting for a message", "Nos conseils": "Our advice", "Pourquoi": "Why", "Collez ici le message suspect…": "Paste the suspicious message here…",
            },
            "es": {
                "Images": "Imágenes", "Texte": "Texto", "Nettoyeur de fichiers": "Limpiador de archivos", "Anti-arnaque": "Antiestafas", "Motifs et mots-clés": "Patrones y palabras clave", "Paramètres": "Ajustes",
                "Langue de l'interface": "Idioma de la interfaz", "Français": "Francés", "Anglais": "Inglés", "Espagnol": "Español", "Apparence": "Apariencia", "Sombre": "Oscuro", "Clair": "Claro",
                "Le changement est immédiat et mémorisé.": "Los cambios se aplican al instante y se guardan.", "Choisir une image": "Elegir una imagen", "Déposez une image ici": "Suelta una imagen aquí", "Anonymiser": "Anonimizar", "Anonymiser à nouveau": "Anonimizar de nuevo", "Enregistrer l'image": "Guardar imagen", "Traitement…": "Procesando…", "Détecter": "Detectar", "Données détectées": "Datos detectados", "Type de masquage": "Tipo de ocultación", "Noir": "Negro", "Flou": "Desenfoque", "Mosaïque": "Pixelado", "Lecture automatique (OCR)": "Reconocimiento automático (OCR)", "Effacer toutes les zones ?": "¿Borrar todas las zonas?", "Effacer": "Borrar", "Réglages modifiés : relancez l'anonymisation": "Ajustes cambiados: vuelve a anonimizar", "Nettoyeur de métadonnées": "Limpiador de metadatos", "Ajouter des fichiers": "Añadir archivos", "Nettoyer": "Limpiar", "Vider la liste": "Vaciar lista", "Analyser le message": "Analizar mensaje", "En attente d'un message": "Esperando un mensaje", "Nos conseils": "Consejos", "Pourquoi": "Por qué", "Collez ici le message suspect…": "Pega aquí el mensaje sospechoso…",
            }
        }
        translations["en"].update({
            "Enregistrer l'image anonymisée": "Save redacted image", "Anonymisez d'abord l'image avant de l'enregistrer.": "Redact the image before saving it.",
            "Anonymisez d'abord l'image.": "Redact the image first.", "Choisissez un emplacement pour enregistrer l’image.": "Choose where to save the image.",
            "Aucun chemin d’enregistrement sélectionné.": "No save location selected.", "Image chargée : ": "Image loaded: ",
            "Ouverture de l'image…": "Opening image…", "Analyse et masquage en cours…": "Analyzing and redacting…",
            "Tracez au moins une zone, ou activez la détection automatique.": "Draw at least one region or enable automatic detection.",
            "Enregistrement impossible : ": "Could not save image: ", "Impossible d'ouvrir la fenêtre d'enregistrement : ": "Could not open the save dialog: ",
            "Sélectionner une zone manuellement": "Select a region manually", "Enregistrer l'image": "Save image",
            "Ajouter des fichiers": "Add files", "Choisir des fichiers": "Choose files", "Déposez vos fichiers ici": "Drop your files here",
            "Nettoyage…": "Cleaning…", "Vider la liste": "Clear list", "Collez ici le message suspect…": "Paste the suspicious message here…",
            "Copier le résultat": "Copy result", "Résultat anonymisé": "Redacted result", "Texte d'origine": "Original text",
            "Modifier": "Edit", "Surligner": "Highlight", "Type de masquage": "Redaction type", "Rétablir (Ctrl+Maj+Z)": "Redo (Ctrl+Shift+Z)",
            "Effacer": "Clear", "Noir": "Black", "Flou": "Blur", "Mosaïque": "Pixelate", "Détecter": "Detect",
            "Motifs & mots-clés": "Patterns & keywords", "Motifs enregistrés": "Saved patterns", "Nouveau mot-clé": "New keyword",
            "Nom du motif": "Pattern name", "Supprimer": "Delete", "Supprimer ce motif ?": "Delete this pattern?", "Supprimer ce mot-clé ?": "Delete this keyword?",
            "Paramètres": "Settings", "Studio d'anonymisation 100 % local. Aucun appel réseau pendant l'utilisation normale : vos documents ne quittent jamais cet ordinateur.": "100% local redaction studio. No network calls during normal use: your documents never leave this computer.",
            "Version ": "Version ", "Langue de l'interface": "Interface language", "Revérifier": "Check again", "Détection des visages": "Face detection", "Si OpenCV est incompatible, réinstallez les dépendances avec le fichier requirements.txt. Un détecteur prêt ne garantit pas la détection de tous les visages, notamment dans les foules.": "If OpenCV is incompatible, reinstall dependencies from requirements.txt. A ready detector does not guarantee detection of every face, especially in crowds."
        })
        translations["es"].update({
            "Enregistrer l'image anonymisée": "Guardar imagen anonimizada", "Anonymisez d'abord l'image avant de l'enregistrer.": "Anonimiza la imagen antes de guardarla.",
            "Anonymisez d'abord l'image.": "Anonimiza primero la imagen.", "Choisissez un emplacement pour enregistrer l’image.": "Elige dónde guardar la imagen.",
            "Aucun chemin d’enregistrement sélectionné.": "No se ha seleccionado ninguna ubicación.", "Image chargée : ": "Imagen cargada: ",
            "Ouverture de l'image…": "Abriendo imagen…", "Analyse et masquage en cours…": "Analizando y ocultando…",
            "Tracez au moins une zone, ou activez la détection automatique.": "Dibuja al menos una zona o activa la detección automática.",
            "Enregistrement impossible : ": "No se pudo guardar la imagen: ", "Impossible d'ouvrir la fenêtre d'enregistrement : ": "No se pudo abrir el diálogo para guardar: ",
            "Sélectionner une zone manuellement": "Seleccionar una zona manualmente", "Enregistrer l'image": "Guardar imagen",
            "Ajouter des fichiers": "Añadir archivos", "Choisir des fichiers": "Elegir archivos", "Déposez vos fichiers ici": "Suelta tus archivos aquí",
            "Nettoyage…": "Limpiando…", "Vider la liste": "Vaciar lista", "Collez ici le message suspect…": "Pega aquí el mensaje sospechoso…",
            "Copier le résultat": "Copiar resultado", "Résultat anonymisé": "Resultado anonimizado", "Texte d'origine": "Texto original",
            "Modifier": "Editar", "Surligner": "Resaltar", "Type de masquage": "Tipo de ocultación", "Rétablir (Ctrl+Maj+Z)": "Rehacer (Ctrl+Mayús+Z)",
            "Effacer": "Borrar", "Noir": "Negro", "Flou": "Desenfoque", "Mosaïque": "Pixelado", "Détecter": "Detectar",
            "Motifs & mots-clés": "Patrones y palabras clave", "Motifs enregistrés": "Patrones guardados", "Nouveau mot-clé": "Nueva palabra clave",
            "Nom du motif": "Nombre del patrón", "Supprimer": "Eliminar", "Supprimer ce motif ?": "¿Eliminar este patrón?", "Supprimer ce mot-clé ?": "¿Eliminar esta palabra clave?",
            "Paramètres": "Ajustes", "Studio d'anonymisation 100 % local. Aucun appel réseau pendant l'utilisation normale : vos documents ne quittent jamais cet ordinateur.": "Estudio de anonimización 100 % local. No hay conexiones de red durante el uso normal: tus documentos nunca salen de este equipo.",
            "Version ": "Versión ", "Langue de l'interface": "Idioma de la interfaz", "Revérifier": "Volver a comprobar", "Détection des visages": "Detección de rostros", "Si OpenCV est incompatible, réinstallez les dépendances avec le fichier requirements.txt. Un détecteur prêt ne garantit pas la détection de tous les visages, notamment dans les foules.": "Si OpenCV es incompatible, reinstala las dependencias desde requirements.txt. Un detector listo no garantiza detectar todos los rostros, especialmente en multitudes."
        })
        translations["en"].update({'Ajouter': 'Add', 'Annuler': 'Cancel', 'Comparer': 'Compare', 'Original': 'Original', 'Pseudonyme': 'Pseudonym', 'Résultat': 'Result', 'Aucun mot-clé.': 'No keywords.', 'Aucun motif personnalisé.': 'No custom patterns.', 'Copie créée': 'Copy created', 'Copier le résultat': 'Copy result', 'Détection automatique des données': 'Automatic data detection', 'Fichier : ': 'File: ', "Journal d'erreurs : ": 'Error log: ', 'Motifs (expressions régulières)': 'Patterns (regular expressions)', 'Motifs enregistrés': 'Saved patterns', 'Mots-clés': 'Keywords', 'Résultat anonymisé': 'Redacted result', 'Test en direct': 'Live test', "Texte d'origine": 'Original text', 'Un mot ou une expression à toujours masquer (sans tenir compte des majuscules).': 'A word or phrase to always redact (case-insensitive).', 'sur 100': 'out of 100', 'Anonymiser un texte': 'Redact text', "Aucun signal d'arnaque connu repéré. Restez prudent : l'analyse est locale et limitée.": 'No known scam signals detected. Stay cautious: this local analysis is limited.', "Auteur, société, GPS, appareil… retirés de vos PDF, documents Office et images. Une copie « _propre » est créée, l'original n'est jamais modifié.": 'Author, company, GPS and device metadata are removed from PDFs, Office documents and images. A “_clean” copy is created; the original is never modified.', 'Choisir des fichiers': 'Choose files', 'Collez un SMS, un e-mail ou un message reçu : Bouclier cherche les signaux typiques du phishing. Rien ne quitte votre ordinateur.': 'Paste an SMS, email or received message: Bouclier looks for typical phishing signals. Nothing leaves your computer.', 'Collez un texte : les données personnelles sont repérées et remplacées au fil de la frappe.': 'Paste text: personal data is detected and replaced as you type.', 'Installer / Réparer automatiquement': 'Install / Repair automatically', 'Motifs & mots-clés': 'Patterns & keywords', 'Raccourcis : Ctrl+O ouvrir · Ctrl+S enregistrer · Ctrl+Z annuler · Ctrl+Maj+Z rétablir · Molette zoom · Espace + glisser pour déplacer': 'Shortcuts: Ctrl+O open · Ctrl+S save · Ctrl+Z undo · Ctrl+Shift+Z redo · Mouse wheel zoom · Space + drag to pan', 'Astuce : tracez un rectangle à la souris pour masquer une zone précise. Molette pour zoomer, Espace + glisser pour déplacer.': 'Tip: draw a rectangle with the mouse to redact a specific area. Mouse wheel to zoom, Space + drag to pan.', 'Déposez vos fichiers ici': 'Drop your files here', 'Enregistrer l’image anonymisée': 'Save redacted image', 'Choisir des fichiers à nettoyer': 'Choose files to clean', 'Le niveau de risque, les raisons et les conseils s’afficheront ici.': 'The risk level, reasons and advice will appear here.', 'Photo, scan, capture d’écran : Bouclier repère les données personnelles et les masque. Tout reste sur votre ordinateur.': 'Photo, scan or screenshot: Bouclier detects and redacts personal data. Everything stays on your computer.', 'Collez ici un texte contenant des noms, adresses, e-mails, téléphones, IBAN…': 'Paste text containing names, addresses, emails, phone numbers, IBANs…', 'Le texte anonymisé apparaîtra ici.': 'The redacted text will appear here.', 'Écrivez un texte d’exemple pour voir ce que le motif détecte…': 'Write sample text to see what the pattern detects…', 'Nom (ex. Dossier)': 'Name (e.g. Folder)', 'Motif (ex. DOS-\\d{4})': 'Pattern (e.g. DOS-\\d{4})', 'Ex. Projet Phoenix': 'E.g. Project Phoenix', 'Déposez une image ici': 'Drop an image here', 'Paramètres': 'Settings'})
        translations["es"].update({'Ajouter': 'Añadir', 'Annuler': 'Cancelar', 'Comparer': 'Comparar', 'Original': 'Original', 'Pseudonyme': 'Seudónimo', 'Résultat': 'Resultado', 'Aucun mot-clé.': 'No hay palabras clave.', 'Aucun motif personnalisé.': 'No hay patrones personalizados.', 'Copie créée': 'Copia creada', 'Copier le résultat': 'Copiar resultado', 'Détection automatique des données': 'Detección automática de datos', 'Fichier : ': 'Archivo: ', "Journal d'erreurs : ": 'Registro de errores: ', 'Motifs (expressions régulières)': 'Patrones (expresiones regulares)', 'Motifs enregistrés': 'Patrones guardados', 'Mots-clés': 'Palabras clave', 'Résultat anonymisé': 'Resultado anonimizado', 'Test en direct': 'Prueba en directo', "Texte d'origine": 'Texto original', 'Un mot ou une expression à toujours masquer (sans tenir compte des majuscules).': 'Una palabra o expresión que siempre se debe ocultar (sin distinguir mayúsculas).', 'sur 100': 'de 100', 'Anonymiser un texte': 'Anonimizar texto', "Aucun signal d'arnaque connu repéré. Restez prudent : l'analyse est locale et limitée.": 'No se detectaron señales conocidas de estafa. Mantén la precaución: este análisis local es limitado.', "Auteur, société, GPS, appareil… retirés de vos PDF, documents Office et images. Une copie « _propre » est créée, l'original n'est jamais modifié.": 'Se eliminan los metadatos de autor, empresa, GPS y dispositivo de PDF, documentos Office e imágenes. Se crea una copia «_limpia»; el original nunca se modifica.', 'Choisir des fichiers': 'Elegir archivos', 'Collez un SMS, un e-mail ou un message reçu : Bouclier cherche les signaux typiques du phishing. Rien ne quitte votre ordinateur.': 'Pega un SMS, correo electrónico o mensaje recibido: Bouclier busca señales típicas de phishing. Nada sale de tu ordenador.', 'Collez un texte : les données personnelles sont repérées et remplacées au fil de la frappe.': 'Pega un texto: los datos personales se detectan y sustituyen mientras escribes.', 'Installer / Réparer automatiquement': 'Instalar / Reparar automáticamente', 'Motifs & mots-clés': 'Patrones y palabras clave', 'Raccourcis : Ctrl+O ouvrir · Ctrl+S enregistrer · Ctrl+Z annuler · Ctrl+Maj+Z rétablir · Molette zoom · Espace + glisser pour déplacer': 'Atajos: Ctrl+O abrir · Ctrl+S guardar · Ctrl+Z deshacer · Ctrl+Mayús+Z rehacer · Rueda para ampliar · Espacio + arrastrar para mover', 'Astuce : tracez un rectangle à la souris pour masquer une zone précise. Molette pour zoomer, Espace + glisser pour déplacer.': 'Consejo: dibuja un rectángulo con el ratón para ocultar una zona. Rueda para ampliar; Espacio + arrastrar para mover.', 'Déposez vos fichiers ici': 'Suelta tus archivos aquí', 'Enregistrer l’image anonymisée': 'Guardar imagen anonimizada', 'Choisir des fichiers à nettoyer': 'Elegir archivos para limpiar', 'Le niveau de risque, les raisons et les conseils s’afficheront ici.': 'Aquí aparecerán el nivel de riesgo, los motivos y los consejos.', 'Photo, scan, capture d’écran : Bouclier repère les données personnelles et les masque. Tout reste sur votre ordinateur.': 'Foto, escaneo o captura: Bouclier detecta y oculta datos personales. Todo permanece en tu ordenador.', 'Collez ici un texte contenant des noms, adresses, e-mails, téléphones, IBAN…': 'Pega texto que contenga nombres, direcciones, correos, teléfonos, IBAN…', 'Le texte anonymisé apparaîtra ici.': 'El texto anonimizado aparecerá aquí.', 'Écrivez un texte d’exemple pour voir ce que le motif détecte…': 'Escribe un texto de ejemplo para ver qué detecta el patrón…', 'Nom (ex. Dossier)': 'Nombre (p. ej., Carpeta)', 'Motif (ex. DOS-\\d{4})': 'Patrón (p. ej., DOS-\\d{4})', 'Ex. Projet Phoenix': 'P. ej., Proyecto Phoenix', 'Déposez une image ici': 'Suelta una imagen aquí', 'Paramètres': 'Ajustes'})
        # Complément de traductions pour les libellés QML et les textes d’accessibilité.
        try:
            import json
            extra_path = Path(__file__).with_name("translations_extra.json")
            extra = json.loads(extra_path.read_text(encoding="utf-8")) if extra_path.exists() else {}
            for lang, mapping in extra.items():
                translations.setdefault(lang, {}).update(mapping)
        except (OSError, ValueError):
            pass
        selected = translations.get(language or self._language, {})
        if text in selected:
            return selected[text]
        # Traduire aussi les messages dynamiques dont la fin contient un nom de fichier ou un détail.
        for source, target in selected.items():
            if source.endswith((" : ", ": ", " ")) and text.startswith(source):
                return target + text[len(source):]
        for pat, per_lang in _DYNAMIC_TR:
            m = re.fullmatch(pat, text)
            if m and (language or self._language) in per_lang:
                return per_lang[language or self._language].format(*m.groups())
        return text

    @Slot(str)
    def setTheme(self, value: str) -> None:
        if value in ("dark", "light") and value != self._theme:
            self._theme = value
            self._settings["theme"] = value
            services.save_settings(self._settings)
            self.themeChanged.emit()

    # -- infos
    @Property(str, constant=True)
    def version(self): return __version__

    @Property(str, constant=True)
    def logPath(self): return str(services.APP_DIR / "bouclier_erreur.log")
    @Property(str, constant=True)
    def faceDetectionStatus(self): return services.face_detector_status()

    @Slot(str, str)
    def notify(self, kind: str, message: str) -> None:
        self.toast.emit(kind, message)

    # -- OCR
    def _get_state(self): return self._ocr_state
    def _get_msg(self): return self._ocr_message
    def _get_inst(self): return self._ocr_installing
    def _get_log(self): return self._ocr_log
    ocrState = Property(str, _get_state, notify=ocrChanged)
    ocrMessage = Property(str, _get_msg, notify=ocrChanged)
    ocrInstalling = Property(bool, _get_inst, notify=ocrChanged)
    ocrLog = Property(str, _get_log, notify=ocrChanged)

    def _set_ocr(self, state=None, message=None, installing=None, log=None) -> None:
        if state is not None: self._ocr_state = state
        if message is not None: self._ocr_message = message
        if installing is not None: self._ocr_installing = installing
        if log is not None: self._ocr_log = log
        self.ocrChanged.emit()

    @Slot()
    def refreshOcr(self) -> None:
        if self._ocr_installing:
            return
        self._set_ocr(state="checking", message="Vérification de l'OCR…")

        def work():
            from .. import ocr_engine
            ocr_engine.reset_detection()
            return ocr_engine.ocr_status()

        def ok(st):
            if st.get("usable"):
                self._set_ocr(state="ready", message=f"OCR prêt (langues : {st.get('lang') or '?'})")
            else:
                self._set_ocr(state="error", message=str(st.get("error") or "OCR indisponible."))

        self._async(work, ok, fail=lambda m: self._set_ocr(state="error", message=m))

    @Slot()
    def installOcr(self) -> None:
        if self._ocr_installing:
            return
        self._set_ocr(installing=True, log="Démarrage de l'installation…")

        def work(progress):
            from .. import ocr_engine, tesseract_setup
            res = tesseract_setup.ensure_ocr(lambda m: progress(str(m).strip()))
            ocr_engine.reset_detection()
            return res

        def ok(res):
            self._set_ocr(installing=False)
            self._notify("success" if res.get("ok") else "warning", str(res.get("message", "")))
            self.refreshOcr()

        self._async(work, ok, fail=lambda m: self._set_ocr(installing=False, state="error", message=m), with_progress=True)

    def _on_progress(self, msg: str) -> None:
        if msg:
            self._set_ocr(log=msg)


# =============================================================================== images
def _entity_key(entity: dict) -> tuple:
    """Identité stable d'une donnée détectée d'une détection à l'autre (les `id` peuvent changer)."""
    return entity.get("type"), entity.get("value"), tuple(tuple(b) for b in entity.get("boxes", []))


class ImageBackend(_Base):
    changed = Signal()
    boxesChanged = Signal()
    entitiesChanged = Signal()

    def __init__(self, app: AppBackend):
        super().__init__(app)
        self._dir = tempfile.mkdtemp(prefix="bouclier_ui_")
        atexit.register(shutil.rmtree, self._dir, True)
        self._reset_state()
        self._mode = "blackout"
        self._auto = True
        self._busy = False
        self._status = ""

    def _reset_state(self):
        self._path = ""
        self._data = None
        self._w = self._h = 0
        self._fmt = "PNG"
        self._src_url = ""
        self._res_url = ""
        self._result = None
        self._stale = False
        self._boxes = []
        self._undo, self._redo = [], []
        self._entities = None
        self._selected = -1
        self._text_warning = ""      # non vide : la dernière détection n'a pas lu le texte
        self._result_unread = False  # le résultat affiché a été produit sans lecture du texte
        self._pages = 1

    # ---- propriétés
    @Property(bool, notify=changed)
    def hasImage(self): return self._data is not None
    @Property(str, notify=changed)
    def sourceUrl(self): return self._src_url
    @Property(str, notify=changed)
    def resultUrl(self): return self._res_url
    @Property(bool, notify=changed)
    def hasResult(self): return self._result is not None
    @Property(bool, notify=changed)
    def stale(self): return self._stale
    @Property(str, notify=changed)
    def textWarning(self): return self._text_warning
    @Property(str, notify=changed)
    def pageWarning(self):
        if self._pages <= 1:
            return ""
        return f"Ce fichier contient {self._pages} pages ou images : seule la première est traitée et enregistrée."
    @Property(int, notify=changed)
    def imageWidth(self): return self._w
    @Property(int, notify=changed)
    def imageHeight(self): return self._h
    @Property(str, notify=changed)
    def fileName(self): return Path(self._path).name if self._path else ""
    @Property(bool, notify=changed)
    def busy(self): return self._busy
    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(str, notify=changed)
    def mode(self): return self._mode
    @Property(bool, notify=changed)
    def autoDetect(self): return self._auto
    @Property(bool, notify=boxesChanged)
    def canUndo(self): return bool(self._undo)
    @Property(bool, notify=boxesChanged)
    def canRedo(self): return bool(self._redo)
    @Property("QVariantList", notify=boxesChanged)
    def boxes(self): return [{"x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3]} for b in self._boxes]
    @Property("QVariantList", notify=entitiesChanged)
    def entities(self): return self._entities or []
    @Property(int, notify=entitiesChanged)
    def selectedEntity(self): return self._selected
    @Property(bool, notify=entitiesChanged)
    def detected(self): return self._entities is not None
    @Property(str, notify=changed)
    def suggestedSavePath(self):
        from PySide6.QtCore import QUrl
        return QUrl.fromLocalFile(services.suggested_name(self._path, self._result_fmt())).toString() if self._path else ""

    def _result_fmt(self) -> str:
        return "JPEG" if self._result and self._result.startswith(b"\xff\xd8") else "PNG"

    def _touch(self, stale: bool = True) -> None:
        if stale:
            self._rev = getattr(self, "_rev", 0) + 1
        if self._result is not None and stale:
            self._stale = True
        self.changed.emit()

    # ---- ouverture
    @Slot(str)
    def openFile(self, value: str) -> None:
        path = services.to_local_path(value)
        if self._busy:
            return
        self._busy, self._status = True, "Ouverture de l'image…"
        self.changed.emit()
        self._async(lambda: services.load_image(path, self._dir), lambda r: self._opened(path, r), fail=self._fail)

    def _opened(self, path, r) -> None:
        from PySide6.QtCore import QUrl
        self._reset_state()
        self._path, self._data, self._w, self._h, self._fmt = path, r["data"], r["width"], r["height"], r["format"]
        self._src_url = QUrl.fromLocalFile(r["preview"]).toString()
        self._pages = r["pages"]
        self._busy, self._status = False, ""
        self.boxesChanged.emit(); self.entitiesChanged.emit(); self.changed.emit()
        self._notify("success", f"Image chargée : {Path(path).name}")
        if self.pageWarning:
            self._notify("warning", self.pageWarning)

    def _fail(self, _msg: str) -> None:
        # _Base._failed affiche déjà l'erreur dans une notification ; ici on remet
        # simplement l'interface dans un état interactif pour permettre une nouvelle tentative.
        self._busy, self._status = False, ""
        self.changed.emit()

    # ---- options
    @Slot(str)
    def setMode(self, mode: str) -> None:
        if mode in ("blackout", "blur", "pixelate") and mode != self._mode:
            self._mode = mode
            self._touch()

    @Slot(bool)
    def setAutoDetect(self, value: bool) -> None:
        if value != self._auto:
            self._auto = value
            self._touch()

    # ---- zones manuelles (coordonnées en pixels image) + annuler/rétablir
    def _clamp(self, x0, y0, x1, y1):
        x0, x1 = sorted((int(round(x0)), int(round(x1))))
        y0, y1 = sorted((int(round(y0)), int(round(y1))))
        return (max(0, x0), max(0, y0), min(self._w, x1), min(self._h, y1))

    def _push(self) -> None:
        self._undo.append(list(self._boxes))
        self._undo = self._undo[-100:]
        self._redo.clear()

    def _boxes_changed(self) -> None:
        self.boxesChanged.emit()
        self._touch()

    @Slot(float, float, float, float)
    def addBox(self, x0, y0, x1, y1) -> None:
        b = self._clamp(x0, y0, x1, y1)
        if b[2] - b[0] < 3 or b[3] - b[1] < 3:
            return
        self._push(); self._boxes.append(b); self._boxes_changed()

    @Slot(int, float, float, float, float)
    def commitBox(self, i, x0, y0, x1, y1) -> None:
        if 0 <= i < len(self._boxes):
            b = self._clamp(x0, y0, x1, y1)
            if b != self._boxes[i] and b[2] - b[0] >= 3 and b[3] - b[1] >= 3:
                self._push(); self._boxes[i] = b
            self._boxes_changed()

    @Slot(int)
    def removeBox(self, i: int) -> None:
        if 0 <= i < len(self._boxes):
            self._push(); del self._boxes[i]; self._boxes_changed()

    @Slot()
    def clearBoxes(self) -> None:
        if self._boxes:
            self._push(); self._boxes = []; self._boxes_changed()

    @Slot()
    def clearAllZones(self) -> None:
        """Efface TOUTES les zones (manuelles + OCR) et l'aperçu anonymisé obsolète."""
        if self._busy:
            self._notify("warning", "Traitement en cours : patientez avant d'effacer les zones.")
            return
        if not (self._boxes or self._entities is not None or self._result is not None):
            return
        if self._boxes:
            self._push()
            self._boxes = []
        # None = « aucune détection » : une nouvelle anonymisation relancera l'OCR.
        self._entities = None
        self._selected = -1
        self._result = None
        self._res_url = ""
        self._stale = False
        self._text_warning, self._result_unread = "", False
        self.boxesChanged.emit()
        self.entitiesChanged.emit()
        self.changed.emit()
        self._notify("success", "Toutes les zones manuelles et OCR ont été effacées.")

    @Slot()
    def undo(self) -> None:
        if self._undo:
            self._redo.append(list(self._boxes)); self._boxes = self._undo.pop(); self._boxes_changed()

    @Slot()
    def redo(self) -> None:
        if self._redo:
            self._undo.append(list(self._boxes)); self._boxes = self._redo.pop(); self._boxes_changed()

    # ---- entités détectées
    @Slot(int)
    def selectEntity(self, i: int) -> None:
        self._selected = i if i != self._selected else -1
        self.entitiesChanged.emit()

    @Slot(int, bool)
    def setEntityExcluded(self, i: int, excluded: bool) -> None:
        if self._entities and 0 <= i < len(self._entities):
            self._entities[i]["excluded"] = bool(excluded)
            self.entitiesChanged.emit()
            self._touch()

    # ---- traitement
    def _set_busy(self, busy: bool, status: str = "") -> None:
        self._busy, self._status = busy, status
        self.changed.emit()

    @Slot()
    def detect(self) -> None:
        """Repère les données (OCR) sans rien masquer, pour les revoir/exclure avant l'export."""
        if self._busy or self._data is None:
            return
        data = self._data
        self._set_busy(True, "Lecture du texte de l'image…")
        self._async(lambda: services.detect_entities(data), self._detected, fail=self._fail)

    def _detected(self, found) -> None:
        self._entities, self._selected = found["entities"], -1
        self._text_warning = found["ocr_error"]
        self._set_busy(False)
        self.entitiesChanged.emit()
        n = len(self._entities)
        if self._text_warning:
            # Ne jamais rassurer : sans lecture du texte, « 0 » ou « visages seuls » ne veut rien dire.
            self._notify("warning" if n else "error", self._text_warning)
            if n:
                self._notify("info", f"Seuls les visages ont été recherchés : {n} repéré(s).")
        else:
            self._notify("success" if n else "info", f"{n} donnée(s) sensible(s) repérée(s)." if n else "Aucune donnée sensible repérée.")

    @Slot()
    def anonymize(self) -> None:
        if self._busy or self._data is None:
            return
        if not self._auto and not self._boxes:
            self._notify("warning", "Tracez au moins une zone, ou activez la détection automatique.")
            return
        data, mode, auto, cached = self._data, self._mode, self._auto, self._entities
        manual = [list(b) for b in self._boxes]
        previous_warning = self._text_warning
        # Une détection faite sans lecture du texte est incomplète : on la relance
        # (Tesseract a pu être installé entre-temps) en conservant les exclusions.
        retry = auto and (cached is None or bool(previous_warning))
        excluded = {_entity_key(e) for e in (cached or []) if e.get("excluded")}
        rev = getattr(self, "_rev", 0)
        self._set_busy(True, "Analyse et masquage en cours…")

        def work():
            # Les résultats OCR en cache ne sont utilisés que si l'option automatique est activée.
            ents, warning = (cached if auto else None), previous_warning
            if retry:
                found = services.detect_entities(data)
                ents, warning = found["entities"], found["ocr_error"]
                for e in ents:
                    e["excluded"] = _entity_key(e) in excluded
            rects = list(manual)
            for e in (ents or []):
                if _entity_key(e) not in excluded:
                    rects.extend(e["boxes"])
            out = {"entities": ents, "new": retry, "warning": warning, "unread": bool(auto and warning),
                   "n_rects": len(rects), "rev": rev, "res": None, "preview": ""}
            # Texte non lu et rien à masquer : produire une image « anonymisée » serait trompeur.
            if not (out["unread"] and not rects):
                out["res"] = services.apply_redaction(data, mode, rects)
                out["preview"] = services.write_preview(out["res"]["data"], self._dir)
            return out

        self._async(work, self._anonymized, fail=self._fail)

    def _anonymized(self, r) -> None:
        from PySide6.QtCore import QUrl
        if r["new"]:
            self._entities, self._selected = r["entities"], -1
            self._text_warning = r["warning"]
        if r["res"] is None:
            self._result, self._res_url, self._stale, self._result_unread = None, "", False, False
            self._set_busy(False)
            self.entitiesChanged.emit()
            self._notify("error", r["warning"])
            self._notify("error", "Rien n'a été masqué et aucune image n'a été produite. Installez ou réparez l'OCR, ou tracez des zones à la souris.")
            return
        self._result = r["res"]["data"]
        self._result_unread = r["unread"]
        self._res_url = QUrl.fromLocalFile(r["preview"]).toString()
        # Zones/options modifiées pendant le traitement : le résultat est déjà périmé.
        self._stale = getattr(self, "_rev", 0) != r["rev"]
        self._set_busy(False)
        self.entitiesChanged.emit()
        n = r["n_rects"]
        if r["unread"]:
            self._notify("warning", r["warning"])
            self._notify("warning", f"Texte NON lu : seules {n} zone(s) (visages et zones manuelles) ont été masquées. Vérifiez l'image avant de la partager.")
        elif n == 0:
            self._notify("info", "Aucune donnée sensible repérée. Métadonnées purgées, image inchangée.")
        else:
            self._notify("success", f"{n} zone(s) masquée(s). Vous pouvez enregistrer l'image.")

    @Slot()
    def saveResultDialog(self) -> None:
        """Ouvre le dialogue natif de sauvegarde, puis enregistre le résultat.

        QFileDialog est plus fiable ici que QtQuick.Dialogs.FileDialog sur certaines
        configurations Windows/Qt où le clic QML ne faisait rien.
        """
        if self._data is None:
            self._notify("warning", "Ouvrez une image avant de l'enregistrer.")
            return
        if self._result is None:
            self._notify("warning", "Anonymisez d'abord l'image avant de l'enregistrer.")
            return
        try:
            from PySide6.QtWidgets import QFileDialog
            suggested = services.suggested_name(self._path, self._result_fmt()) if self._path else "image_anonymisee.png"
            filters = "Images PNG (*.png);;Images JPEG (*.jpg *.jpeg)"
            path, _selected_filter = QFileDialog.getSaveFileName(
                None,
                self._app.tr("Enregistrer l'image anonymisée", self._app.language) if self._app else "Enregistrer l'image anonymisée",
                suggested,
                filters,
                "Images PNG (*.png)"
            )
            if not path:
                return
            self.saveResult(path)
        except Exception as exc:
            services.log_error("Ouverture du dialogue d'enregistrement :\n" + traceback.format_exc())
            self._notify("error", f"Impossible d'ouvrir la fenêtre d'enregistrement : {exc}")
    @Slot(str)
    def saveResult(self, value: str) -> None:
        if self._result is None:
            self._notify("warning", "Anonymisez d'abord l'image.")
            return
        path = services.to_local_path((value or "").strip())
        if not path:
            self._notify("warning", "Choisissez un emplacement pour enregistrer l’image.")
            return
        ext = ".jpg" if self._result_fmt() == "JPEG" else ".png"
        chosen_ext = Path(path).suffix.lower()
        if not chosen_ext:
            path += ext
            chosen_ext = ext
        elif chosen_ext not in (".jpg", ".jpeg", ".png"):
            path += ext
            chosen_ext = ext
        try:
            payload = self._result
            # L'extension choisie par l'utilisateur doit correspondre au format réel du fichier.
            if (chosen_ext in (".jpg", ".jpeg")) != (self._result_fmt() == "JPEG"):
                import io
                from PIL import Image
                with Image.open(io.BytesIO(self._result)) as image:
                    out = io.BytesIO()
                    if chosen_ext in (".jpg", ".jpeg"):
                        image.convert("RGB").save(out, format="JPEG", quality=95, subsampling=0)
                    else:
                        image.save(out, format="PNG", optimize=True)
                    payload = out.getvalue()
            services.save_bytes(path, payload)
            self._notify("success", f"Image enregistrée : {Path(path).name}")
            if self.pageWarning:
                self._notify("warning", self.pageWarning)
            if self._result_unread:
                self._notify("warning", "Attention : le texte de cette image n'a pas été lu. Vérifiez-la avant de la partager.")
        except Exception as e:  # noqa: BLE001
            services.log_error(traceback.format_exc())
            self._notify("error", f"Enregistrement impossible : {e}")


# =============================================================================== texte
class TextBackend(_Base):
    changed = Signal()

    def __init__(self, app: AppBackend):
        super().__init__(app)
        self._kinds = services.text_kinds()
        self._style = "placeholder"
        self._result = {"redacted": "", "count": 0, "findings": [], "sourceHtml": "", "resultHtml": ""}
        self._gen = 0
        self._text = ""

    @Property("QVariantList", notify=changed)
    def kinds(self): return self._kinds
    @Property(str, notify=changed)
    def style(self): return self._style
    @Property(str, notify=changed)
    def redacted(self): return self._result["redacted"]
    @Property(str, notify=changed)
    def sourceHtml(self): return self._result["sourceHtml"]
    @Property(str, notify=changed)
    def resultHtml(self): return self._result["resultHtml"]
    @Property(int, notify=changed)
    def count(self): return self._result["count"]
    @Property("QVariantList", notify=changed)
    def findings(self): return self._result["findings"]

    @Slot(str, bool)
    def setKind(self, key: str, on: bool) -> None:
        for k in self._kinds:
            if k["key"] == key:
                k["on"] = bool(on)
        self.changed.emit()
        self.process(self._text)

    @Slot(str)
    def setStyle(self, style: str) -> None:
        if style in ("placeholder", "stars", "pseudonym"):
            self._style = style
            self.changed.emit()
            self.process(self._text)

    @Slot(str)
    def process(self, text: str) -> None:
        self._text = text
        self._gen += 1
        gen = self._gen
        kinds = {k["key"] for k in self._kinds if k["on"]}
        style = self._style
        if not text.strip():
            self._result = {"redacted": "", "count": 0, "findings": [], "sourceHtml": "", "resultHtml": ""}
            self.changed.emit()
            return
        self._async(lambda: services.analyze_text(text, kinds, style),
                    lambda r, g=gen: self._done(r, g))

    def _done(self, r, gen) -> None:
        if gen == self._gen:  # ignore les résultats périmés
            self._result = r
            self.changed.emit()

    @Slot()
    def copyResult(self) -> None:
        if self._result["redacted"]:
            QGuiApplication.clipboard().setText(self._result["redacted"])
            self._notify("success", "Résultat copié dans le presse-papiers.")
        else:
            self._notify("info", "Rien à copier pour l'instant.")


# =============================================================================== nettoyeur par lot
class CleanerModel(QAbstractListModel):
    NameRole, PathRole, StatusRole, FoundRole, MessageRole, SizeRole, OutRole, WarningsRole = range(Qt.UserRole + 1, Qt.UserRole + 9)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()): return 0 if parent.isValid() else len(self.rows)

    def roleNames(self):
        return {self.NameRole: QByteArray(b"name"), self.PathRole: QByteArray(b"path"),
                self.StatusRole: QByteArray(b"status"), self.FoundRole: QByteArray(b"found"),
                self.MessageRole: QByteArray(b"message"), self.SizeRole: QByteArray(b"size"),
                self.OutRole: QByteArray(b"output"), self.WarningsRole: QByteArray(b"warnings")}

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.rows):
            return None
        r = self.rows[index.row()]
        return {self.NameRole: r["name"], self.PathRole: r["path"], self.StatusRole: r["status"],
                self.FoundRole: r["found"], self.MessageRole: r["message"], self.SizeRole: r["size"],
                self.OutRole: r["output"], self.WarningsRole: r["warnings"]}.get(role)

    def add(self, row) -> None:
        self.beginInsertRows(QModelIndex(), len(self.rows), len(self.rows))
        self.rows.append(row)
        self.endInsertRows()

    def update(self, i, **kw) -> None:
        if 0 <= i < len(self.rows):
            self.rows[i].update(kw)
            self.dataChanged.emit(self.index(i), self.index(i))

    def remove(self, i) -> None:
        if 0 <= i < len(self.rows):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self.rows[i]
            self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.rows = []
        self.endResetModel()


class CleanerBackend(_Base):
    changed = Signal()

    def __init__(self, app: AppBackend):
        super().__init__(app)
        self.model = CleanerModel(self)
        self._running = False
        self._done = 0

    @Property(QObject, constant=True)
    def files(self): return self.model
    @Property(bool, notify=changed)
    def running(self): return self._running
    @Property(int, notify=changed)
    def total(self): return len(self.model.rows)
    @Property(int, notify=changed)
    def doneCount(self): return self._done
    @Property(int, notify=changed)
    def pendingCount(self): return sum(1 for r in self.model.rows if r["status"] in ("pending", "error_retry"))

    @Slot("QVariantList")
    def addFiles(self, urls) -> None:
        exts = services.supported_exts()
        known = {r["path"] for r in self.model.rows}
        added = rejected = 0
        for u in urls:
            path = services.to_local_path(str(u))
            if path in known:
                continue
            p = Path(path)
            if p.is_dir():
                continue
            if p.suffix.lower() not in exts:
                rejected += 1
                continue
            self.model.add({"name": p.name, "path": path, "status": "pending", "found": [], "message": "",
                            "size": "", "output": "", "warnings": []})
            added += 1
        if rejected:
            self._notify("warning", f"{rejected} fichier(s) ignoré(s) : format non pris en charge.")
        self.changed.emit()

    @Slot(int)
    def removeAt(self, i: int) -> None:
        if not self._running:
            self.model.remove(i)
            self.changed.emit()

    @Slot()
    def clear(self) -> None:
        if not self._running:
            self.model.clear()
            self._done = 0
            self.changed.emit()

    @Slot()
    def run(self) -> None:
        if self._running:
            return
        todo = [(i, r["path"]) for i, r in enumerate(self.model.rows) if r["status"] in ("pending", "error")]
        if not todo:
            self._notify("info", "Ajoutez des fichiers à nettoyer.")
            return
        self._running, self._done = True, 0
        for i, _ in todo:
            self.model.update(i, status="pending", message="")
        self.changed.emit()

        def work(progress):
            out = []
            for i, path in todo:
                self._dispatchSig.emit(lambda i=i: self.model.update(i, status="running"))
                try:
                    res = services.clean_path(path)
                    out.append((i, "done", res, ""))
                    self._dispatchSig.emit(lambda i=i, res=res: self._file_done(i, res))
                except Exception as e:  # noqa: BLE001 — un fichier en échec ne bloque pas le lot
                    msg, unexpected = services.format_exception(e)
                    if unexpected:
                        services.log_error(f"Nettoyage de {path} :\n" + traceback.format_exc())
                    out.append((i, "error", None, msg))
                    self._dispatchSig.emit(lambda i=i, msg=msg: self._file_error(i, msg))
            return out

        self._async(work, self._finished, fail=lambda m: self._end(), with_progress=True)

    def _file_done(self, i, res) -> None:
        self._done += 1
        self.model.update(i, status="done", found=res["found"], warnings=res["warnings"], output=res["output"],
                          size=f"{services.human_size(res['before'])} → {services.human_size(res['after'])}")
        self.changed.emit()

    def _file_error(self, i, msg) -> None:
        self._done += 1
        self.model.update(i, status="error", message=msg)
        self.changed.emit()

    def _finished(self, out) -> None:
        ok = sum(1 for o in out if o[1] == "done")
        bad = len(out) - ok
        to_check = sum(1 for o in out if o[2] and o[2]["warnings"])
        self._end()
        self._notify("success" if not bad else "warning",
                     f"{ok} fichier(s) nettoyé(s)" + (f", {bad} en erreur." if bad else ". Copies « _propre » créées."))
        if to_check:
            self._notify("warning", f"{to_check} fichier(s) à vérifier : certains éléments n'ont pas pu être nettoyés.")

    def _end(self) -> None:
        self._running = False
        self.changed.emit()


# =============================================================================== anti-arnaque
class ScamBackend(_Base):
    changed = Signal()

    def __init__(self, app: AppBackend):
        super().__init__(app)
        self._res = None

    @Property(bool, notify=changed)
    def analyzed(self): return self._res is not None
    @Property(int, notify=changed)
    def score(self): return self._res["score"] if self._res else 0
    @Property(str, notify=changed)
    def level(self): return self._res["level"] if self._res else "low"
    @Property(str, notify=changed)
    def label(self): return self._res["label"] if self._res else ""
    @Property("QVariantList", notify=changed)
    def reasons(self): return self._res["reasons"] if self._res else []
    @Property("QVariantList", notify=changed)
    def advice(self): return self._res["advice"] if self._res else []

    @Slot(str)
    def analyze(self, text: str) -> None:
        if not text.strip():
            self._notify("info", "Collez d'abord un message à analyser.")
            return
        try:
            from .. import scam
            self._res = scam.analyze(text)
        except Exception as e:  # noqa: BLE001
            services.log_error(traceback.format_exc())
            self._notify("error", f"Analyse impossible : {e}")
            return
        self.changed.emit()

    @Slot()
    def reset(self) -> None:
        self._res = None
        self.changed.emit()


# =============================================================================== motifs & mots-clés
class PatternsBackend(_Base):
    changed = Signal()

    def __init__(self, app: AppBackend):
        super().__init__(app)

    @Property("QVariantList", notify=changed)
    def patterns(self):
        from .. import ner_engine
        return [{"id": p["id"], "label": p.get("label", ""), "regex": p.get("regex", "")}
                for p in ner_engine.registry.custom_patterns()]

    @Property("QVariantList", notify=changed)
    def keywords(self):
        from .. import ner_engine
        return sorted(ner_engine.registry.custom_keywords, key=str.lower)

    @Slot(str, str)
    def addPattern(self, label: str, regex: str) -> None:
        from .. import ner_engine
        check = services.try_pattern(regex, "")
        if not label.strip():
            self._notify("warning", "Donnez un nom à ce motif.")
        elif not check["valid"]:
            self._notify("error", check["error"] or "Motif invalide.")
        elif ner_engine.registry.add_custom_pattern(label, regex):
            self._notify("success", f"Motif « {label.strip()} » ajouté.")
            self.changed.emit()
        else:
            self._notify("error", "Motif refusé ou enregistrement impossible (voir bouclier_patterns.json).")

    @Slot(str)
    def removePattern(self, pattern_id: str) -> None:
        from .. import ner_engine
        ner_engine.registry.remove_pattern(pattern_id)
        self.changed.emit()
        self._notify("info", "Motif supprimé.")

    @Slot(str)
    def addKeyword(self, word: str) -> None:
        from .. import ner_engine
        if ner_engine.registry.add_keyword(word):
            self._notify("success", f"Mot-clé « {word.strip()} » ajouté.")
            self.changed.emit()
        else:
            self._notify("warning", "Mot-clé trop court (2 caractères minimum) ou non enregistrable.")

    @Slot(str)
    def removeKeyword(self, word: str) -> None:
        from .. import ner_engine
        ner_engine.registry.remove_keyword(word)
        self.changed.emit()
        self._notify("info", "Mot-clé supprimé.")

    @Slot(str, str, result="QVariantMap")
    def testPattern(self, regex: str, sample: str):
        return services.try_pattern(regex, sample)
