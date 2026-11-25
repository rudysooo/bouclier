import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth
        clip: true
        ColumnLayout {
            x: Theme.space5; y: Theme.space5
            width: Math.min(720, parent.width - 2 * Theme.space5)
            spacing: Theme.space4

            AppText { text: appBackend.tr("Paramètres", appBackend.language); role: "title" }

            Card {
                Layout.fillWidth: true; implicitHeight: a.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: a; anchors.left: parent.left; anchors.right: parent.right; spacing: Theme.space3
                    AppText { text: appBackend.tr("Apparence", appBackend.language); role: "lead" }
                    AppText { text: appBackend.tr("Le changement est immédiat et mémorisé.", appBackend.language); role: "small" }
                    SegmentedControl {
                        Layout.preferredWidth: 300
                        current: appBackend.theme
                        options: [{ value: "dark", label: appBackend.tr("Sombre", appBackend.language), icon: "moon" }, { value: "light", label: appBackend.tr("Clair", appBackend.language), icon: "sun" }]
                        onPicked: (v) => appBackend.setTheme(v)
                    }
                }
            }

            Card {
                Layout.fillWidth: true; implicitHeight: l.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: l; anchors.left: parent.left; anchors.right: parent.right; spacing: Theme.space3
                    AppText { text: appBackend.tr("Langue de l'interface", appBackend.language); role: "lead" }
                    SegmentedControl {
                        Layout.preferredWidth: 390
                        current: appBackend.language
                        options: [{ value: "fr", label: appBackend.tr("Français", appBackend.language) }, { value: "en", label: appBackend.tr("Anglais", appBackend.language) }, { value: "es", label: appBackend.tr("Espagnol", appBackend.language) }]
                        onPicked: (v) => appBackend.setLanguage(v)
                    }
                    AppText { text: appBackend.tr("Le changement est immédiat et mémorisé.", appBackend.language); role: "small"; Layout.fillWidth: true }
                }
            }

            Card {
                Layout.fillWidth: true; implicitHeight: o.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: o; anchors.left: parent.left; anchors.right: parent.right; spacing: Theme.space3
                    RowLayout {
                        Rectangle { width: 10; height: 10; radius: 5; Layout.alignment: Qt.AlignVCenter
                                    color: appBackend.ocrState === "ready" ? Theme.accent : appBackend.ocrState === "error" ? Theme.danger : Theme.warning }
                        AppText { text: appBackend.tr("Lecture automatique (OCR)", appBackend.language); role: "lead"; Layout.fillWidth: true }
                    }
                    AppText { text: appBackend.tr(appBackend.ocrInstalling ? appBackend.ocrLog : appBackend.ocrMessage, appBackend.language); Layout.fillWidth: true; role: "muted" }
                    AppProgress { visible: appBackend.ocrInstalling; indeterminate: true; Layout.fillWidth: true }
                    RowLayout {
                        spacing: Theme.space2
                        AppButton { text: appBackend.tr("Revérifier", appBackend.language); iconName: "refresh"; enabled: !appBackend.ocrInstalling; onClicked: appBackend.refreshOcr() }
                        AppButton { text: appBackend.tr("Installer / Réparer automatiquement", appBackend.language); iconName: "wand"; variant: "primary"
                                    enabled: !appBackend.ocrInstalling; onClicked: appBackend.installOcr() }
                    }
                    AppText { text: appBackend.tr("L'installation télécharge Tesseract et les langues français/anglais (connexion internet nécessaire à cette seule étape). Windows peut demander une autorisation administrateur.", appBackend.language)
                              role: "small"; Layout.fillWidth: true }
                }
            }

            Card {
                Layout.fillWidth: true; implicitHeight: faceStatus.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: faceStatus; anchors.left: parent.left; anchors.right: parent.right; spacing: Theme.space2
                    AppText { text: appBackend.tr("Détection des visages", appBackend.language); role: "lead" }
                    AppText { text: appBackend.faceDetectionStatus; role: "muted"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    AppText { text: appBackend.tr("Si OpenCV est incompatible, réinstallez les dépendances avec le fichier requirements.txt. Un détecteur prêt ne garantit pas la détection de tous les visages, notamment dans les foules.", appBackend.language); role: "small"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                }
            }

            Card {
                Layout.fillWidth: true; implicitHeight: b.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: b; anchors.left: parent.left; anchors.right: parent.right; spacing: Theme.space2
                    RowLayout {
                        spacing: Theme.space3
                        Image { source: Qt.resolvedUrl("../../assets/logo.svg"); sourceSize: Qt.size(96, 96); Layout.preferredWidth: 40; Layout.preferredHeight: 40 }
                        ColumnLayout {
                            spacing: 0
                            AppText { text: appBackend.tr("Bouclier", appBackend.language); role: "lead" }
                            AppText { text: appBackend.tr("Version ", appBackend.language) + appBackend.version; role: "small" }
                        }
                    }
                    AppText { text: appBackend.tr("Studio d'anonymisation 100 % local. Aucun appel réseau pendant l'utilisation normale : vos documents ne quittent jamais cet ordinateur.", appBackend.language)
                              role: "muted"; Layout.fillWidth: true }
                    AppText {
                        text: appBackend.tr("Créé par Polaether · ", appBackend.language) + "polaether.polaether.workers.dev"
                        role: "small"; color: Theme.accentFg; Layout.fillWidth: true
                        Accessible.name: text; Accessible.role: Accessible.Link
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally("https://polaether.polaether.workers.dev/") }
                    }
                    AppText { text: appBackend.tr("Journal d'erreurs : ", appBackend.language) + appBackend.logPath; role: "small"; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                    AppText { text: appBackend.tr("Raccourcis : Ctrl+O ouvrir · Ctrl+S enregistrer · Ctrl+Z annuler · Ctrl+Maj+Z rétablir · Molette zoom · Espace + glisser pour déplacer", appBackend.language)
                              role: "small"; Layout.fillWidth: true }
                }
            }
        }
    }
}
