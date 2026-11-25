import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import "../components"

Item {
    id: page
    function openDialog() { dlg.open() }

    FileDialog {
        id: dlg
        title: appBackend.tr("Choisir des fichiers à nettoyer", appBackend.language)
        fileMode: FileDialog.OpenFiles
        nameFilters: appBackend.language === "en" ? ["Documents and images (*.pdf *.docx *.xlsx *.pptx *.jpg *.jpeg *.png *.webp *.tif *.tiff)", "All files (*)"] : ["Documents et images (*.pdf *.docx *.xlsx *.pptx *.jpg *.jpeg *.png *.webp *.tif *.tiff)", "Tous les fichiers (*)"]
        onAccepted: cleanerBackend.addFiles(selectedFiles.map(String))
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2
                AppText { text: appBackend.tr("Nettoyeur de métadonnées", appBackend.language); role: "title" }
                AppText { text: appBackend.tr("Auteur, société, GPS, appareil… retirés de vos PDF, documents Office et images. Une copie « _propre » est créée, l'original n'est jamais modifié.", appBackend.language)
                          role: "muted"; Layout.fillWidth: true; Layout.maximumWidth: 640 }
            }
            Item { Layout.fillWidth: true }
            AppButton { text: appBackend.tr("Vider la liste", appBackend.language); variant: "ghost"; iconName: "trash"; enabled: cleanerBackend.total > 0 && !cleanerBackend.running; onClicked: cleanerBackend.clear() }
            AppButton { text: appBackend.tr("Ajouter des fichiers", appBackend.language); iconName: "plus"; onClicked: page.openDialog(); enabled: !cleanerBackend.running }
            AppButton {
                text: cleanerBackend.running ? appBackend.tr("Nettoyage…", appBackend.language) : appBackend.tr("Nettoyer", appBackend.language)
                variant: "primary"; iconName: "broom"
                enabled: cleanerBackend.total > 0 && !cleanerBackend.running
                onClicked: cleanerBackend.run()
            }
        }

        AppProgress { Layout.fillWidth: true; visible: cleanerBackend.running
                      value: cleanerBackend.total ? cleanerBackend.doneCount / cleanerBackend.total : 0 }

        Item {
            Layout.fillWidth: true; Layout.fillHeight: true

            DropZone {
                anchors.fill: parent
                visible: cleanerBackend.total === 0
                onActivated: page.openDialog()
                onDropped: (urls) => cleanerBackend.addFiles(urls.map(String))
                EmptyState {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 48, 460)
                    iconName: "broom"
                    title: appBackend.tr("Déposez vos fichiers ici", appBackend.language)
                    subtitle: appBackend.tr("PDF, Word, Excel, PowerPoint, JPEG, PNG, WebP, TIFF. Vous pouvez en déposer plusieurs à la fois.", appBackend.language)
                    AppButton { text: appBackend.tr("Choisir des fichiers", appBackend.language); iconName: "upload"; variant: "primary"; onClicked: page.openDialog() }
                }
            }

            ListView {
                id: list
                anchors.fill: parent
                visible: cleanerBackend.total > 0
                clip: true
                spacing: Theme.space2
                model: cleanerBackend.files
                ScrollBar.vertical: ScrollBar { }
                DropArea { anchors.fill: parent; onDropped: (d) => { if (d.hasUrls) cleanerBackend.addFiles(d.urls.map(String)) } }
                add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.durMed } }

                delegate: Card {
                    id: row
                    property bool open: false
                    width: list.width - 12
                    height: (open ? 74 + details.implicitHeight + 8 : 64)
                    elevated: false
                    padding: 0
                    Behavior on height { NumberAnimation { duration: Theme.durMed; easing.type: Theme.easing } }
                    clip: true

                    MouseArea { anchors.fill: parent; anchors.bottomMargin: parent.height - 64; cursorShape: Qt.PointingHandCursor
                                enabled: status === "done"; onClicked: row.open = !row.open }
                    RowLayout {
                        x: Theme.space4; y: 0; width: parent.width - 2 * Theme.space4; height: 64
                        spacing: Theme.space3
                        Rectangle {
                            width: 36; height: 36; radius: Theme.radiusS + 2
                            color: status === "done" ? Theme.accentSoft : status === "error" ? Theme.dangerSoft : Theme.surfaceHi
                            Icon { anchors.centerIn: parent; name: status === "done" ? "check" : status === "error" ? "alert" : "file"
                                   color: status === "done" ? Theme.accentFg : status === "error" ? Theme.danger : Theme.textMuted }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true; spacing: 2
                            AppText { text: name; Layout.fillWidth: true; elide: Text.ElideMiddle; wrapMode: Text.NoWrap; font.weight: Font.Medium }
                            AppText {
                                Layout.fillWidth: true; role: "small"; elide: Text.ElideRight; wrapMode: Text.NoWrap
                                color: status === "error" ? Theme.danger : Theme.textMuted
                                text: status === "pending" ? appBackend.tr("En attente", appBackend.language)
                                    : status === "running" ? appBackend.tr("Nettoyage en cours…", appBackend.language)
                                    : status === "error" ? message
                                    : (warnings.length ? warnings.length + " " + appBackend.tr("élément(s) non nettoyé(s) · ", appBackend.language) : "")
                                      + (found.length ? found.length + appBackend.tr("métadonnée(s) retirée(s) · ", appBackend.language) : appBackend.tr("Aucune métadonnée trouvée · ", appBackend.language)) + size
                            }
                        }
                        AppProgress { visible: status === "running"; indeterminate: true; Layout.preferredWidth: 90 }
                        Badge { visible: status === "done"; text: warnings.length ? appBackend.tr("À vérifier", appBackend.language) : appBackend.tr("Copie créée", appBackend.language)
                                tone: warnings.length ? "warning" : "success" }
                        IconButton { iconName: "x"; tip: appBackend.tr("Retirer de la liste", appBackend.language); size: 32; enabled: !cleanerBackend.running; onClicked: cleanerBackend.removeAt(index) }
                    }
                    Column {
                        id: details
                        x: Theme.space4 + 48; y: 68; width: parent.width - x - Theme.space4
                        spacing: 4
                        visible: row.open
                        Repeater {
                            model: warnings
                            delegate: AppText { text: "• " + appBackend.tr(modelData, appBackend.language); role: "small"; color: Theme.warning; width: details.width }
                        }
                        Repeater {
                            model: found
                            delegate: AppText { text: "• " + appBackend.tr(modelData, appBackend.language); role: "small"; width: details.width }
                        }
                        AppText { text: appBackend.tr("Fichier : ", appBackend.language) + output; role: "small"; color: Theme.textFaint; width: details.width }
                    }
                }
            }
        }
    }
}
