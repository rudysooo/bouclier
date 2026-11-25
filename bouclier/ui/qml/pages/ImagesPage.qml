import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property string view: "original"          // original | result | compare
    property string lastRes: ""

    function openDialog() { openDlg.open() }
    function saveDialog() {
        if (!imageBackend.hasResult) {
            appBackend.notify("warning", appBackend.tr("Anonymisez d'abord l'image avant de l'enregistrer.", appBackend.language))
            return
        }
        saveDlg.currentFile = imageBackend.suggestedSavePath
        saveDlg.open()
    }
    function undo() { imageBackend.undo() }
    function redo() { imageBackend.redo() }

    FileDialog {
        id: openDlg
        title: appBackend.tr("Choisir une image", appBackend.language)
        nameFilters: appBackend.language === "en" ? ["Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)", "All files (*)"] : ["Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)", "Tous les fichiers (*)"]
        onAccepted: imageBackend.openFile(String(selectedFile))
    }
    FileDialog {
        id: saveDlg
        title: appBackend.tr("Enregistrer l'image anonymisée", appBackend.language)
        fileMode: FileDialog.SaveFile
        nameFilters: ["Images PNG (*.png)", "Images JPEG (*.jpg *.jpeg)"]
        defaultSuffix: "png"
        onAccepted: imageBackend.saveResult(String(selectedFile))
    }
    Connections {
        target: imageBackend
        function onChanged() {
            if (imageBackend.resultUrl !== page.lastRes) {
                page.lastRes = imageBackend.resultUrl
                page.view = imageBackend.resultUrl !== "" ? "result" : "original"
            }
        }
    }
    // glisser une nouvelle image n'importe où sur la page
    DropArea {
        anchors.fill: parent
        onDropped: (d) => { if (d.hasUrls) imageBackend.openFile(String(d.urls[0])) }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        // ============================================================ zone image
        Card {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0

            Item {
                anchors.fill: parent
                anchors.margins: 1

                // état vide
                DropZone {
                    anchors.fill: parent
                    anchors.margins: Theme.space4
                    visible: !imageBackend.hasImage
                    onActivated: page.openDialog()
                    onDropped: (urls) => imageBackend.openFile(String(urls[0]))
                    EmptyState {
                        anchors.centerIn: parent
                        width: Math.min(parent.width - 48, 460)
                        iconName: "image"
                        title: appBackend.tr("Déposez une image ici", appBackend.language)
                        subtitle: appBackend.tr("Photo, scan, capture d'écran : Bouclier repère les données personnelles et les masque. Tout reste sur votre ordinateur.", appBackend.language)
                        AppButton { text: appBackend.tr("Choisir une image", appBackend.language); iconName: "upload"; variant: "primary"; onClicked: page.openDialog() }
                    }
                }

                // image + zones
                Item {
                    id: host
                    anchors.fill: parent
                    visible: imageBackend.hasImage
                    layer.enabled: true
                    layer.effect: MultiEffect { maskEnabled: true; maskSource: mask }
                    ImageCanvas {
                        id: canvas
                        anchors.fill: parent
                        source: imageBackend.sourceUrl
                        resultSource: imageBackend.resultUrl
                        imgW: imageBackend.imageWidth
                        imgH: imageBackend.imageHeight
                        boxes: imageBackend.boxes
                        entities: imageBackend.entities
                        selectedEntity: imageBackend.selectedEntity
                        showResult: imageBackend.hasResult && page.view !== "original"
                        compare: page.view === "compare"
                        onBoxAdded: (a, b, c, d) => { page.view = "original"; imageBackend.addBox(a, b, c, d) }
                        onBoxCommitted: (i, a, b, c, d) => imageBackend.commitBox(i, a, b, c, d)
                        onBoxRemoved: (i) => imageBackend.removeBox(i)
                    }
                    // barre d'actions flottante (haut gauche)
                    Rectangle {
                        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: Theme.space3
                        height: 44; width: bar.implicitWidth + 16; radius: Theme.radiusM
                        color: Theme.surfaceTop; border.width: 1; border.color: Theme.borderStrong
                        Row {
                            id: bar
                            anchors.centerIn: parent
                            spacing: 2
                            IconButton { iconName: "undo"; tip: appBackend.tr("Annuler (Ctrl+Z)", appBackend.language); size: 32; enabled: imageBackend.canUndo; onClicked: imageBackend.undo() }
                            IconButton { iconName: "redo"; tip: appBackend.tr("Rétablir (Ctrl+Maj+Z)", appBackend.language); size: 32; enabled: imageBackend.canRedo; onClicked: imageBackend.redo() }
                            IconButton { iconName: "trash"; tip: appBackend.tr("Effacer toutes les zones", appBackend.language); size: 32; enabled: imageBackend.boxes.length > 0 || imageBackend.entities.length > 0 || imageBackend.hasResult; onClicked: clearDlg.open() }
                            Rectangle { width: 1; height: 20; color: Theme.border; anchors.verticalCenter: parent.verticalCenter }
                            IconButton { iconName: "upload"; tip: appBackend.tr("Ouvrir une autre image (Ctrl+O)", appBackend.language); size: 32; onClicked: page.openDialog() }
                        }
                    }
                    // sélecteur avant/après (haut centre)
                    SegmentedControl {
                        visible: imageBackend.hasResult
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: Theme.space3
                        width: 330
                        current: page.view
                        options: [{ value: "original", label: appBackend.tr("Original", appBackend.language) }, { value: "compare", label: appBackend.tr("Comparer", appBackend.language) }, { value: "result", label: appBackend.tr("Résultat", appBackend.language) }]
                        onPicked: (v) => page.view = v
                    }
                    // fichier à plusieurs pages : les autres seront absentes du résultat
                    Rectangle {
                        visible: imageBackend.pageWarning !== ""
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.top: parent.top; anchors.topMargin: 64
                        width: Math.min(parent.width - 2 * Theme.space3, 440)
                        height: pagesText.implicitHeight + 2 * Theme.space2
                        radius: Theme.radiusS + 2
                        color: Theme.warningSoft; border.width: 1; border.color: Theme.warning
                        AppText {
                            id: pagesText
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                            anchors.margins: Theme.space2
                            role: "small"; color: Theme.warning; horizontalAlignment: Text.AlignHCenter
                            text: appBackend.tr(imageBackend.pageWarning, appBackend.language)
                            Accessible.role: Accessible.AlertMessage; Accessible.name: text
                        }
                    }
                    // indication d'occupation
                    Rectangle {
                        visible: imageBackend.busy
                        anchors.fill: parent
                        color: Theme.scrim
                        MouseArea { anchors.fill: parent; hoverEnabled: true }
                        Column {
                            anchors.centerIn: parent
                            spacing: Theme.space3
                            width: 280
                            AppText { text: appBackend.tr(imageBackend.status, appBackend.language); role: "lead"; width: parent.width; horizontalAlignment: Text.AlignHCenter }
                            AppProgress { indeterminate: true; width: parent.width }
                        }
                    }
                }
                Rectangle {   // masque arrondi
                    id: mask
                    anchors.fill: parent
                    radius: Theme.radiusL - 1
                    visible: false
                    layer.enabled: true
                }
            }
        }

        // ============================================================ panneau de droite
        ColumnLayout {
            Layout.preferredWidth: Theme.panelWidth
            Layout.maximumWidth: Theme.panelWidth
            Layout.fillHeight: true
            spacing: Theme.space3

            // --- état de l'OCR
            Card {
                Layout.fillWidth: true
                implicitHeight: ocrCol.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: ocrCol
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: Theme.space2
                    RowLayout {
                        spacing: Theme.space2
                        Rectangle {
                            width: 10; height: 10; radius: 5
                            color: appBackend.ocrState === "ready" ? Theme.accent : appBackend.ocrState === "error" ? Theme.danger : Theme.warning
                            SequentialAnimation on opacity {
                                running: appBackend.ocrState === "checking" || appBackend.ocrInstalling
                                loops: Animation.Infinite
                                NumberAnimation { to: 0.3; duration: 500 }
                                NumberAnimation { to: 1; duration: 500 }
                            }
                        }
                        AppText { text: appBackend.tr("Lecture automatique (OCR)", appBackend.language); role: "lead"; Layout.fillWidth: true }
                    }
                    AppText {
                        text: appBackend.tr(appBackend.ocrInstalling ? appBackend.ocrLog : appBackend.ocrMessage, appBackend.language)
                        role: "small"; Layout.fillWidth: true; maximumLineCount: 4; elide: Text.ElideRight
                    }
                    AppProgress { visible: appBackend.ocrInstalling; indeterminate: true; Layout.fillWidth: true }
                    AppButton {
                        visible: appBackend.ocrState === "error" && !appBackend.ocrInstalling
                        text: appBackend.tr("Installer / Réparer automatiquement", appBackend.language); iconName: "wand"; variant: "primary"
                        Layout.fillWidth: true
                        onClicked: appBackend.installOcr()
                    }
                }
            }

            // --- réglages de masquage
            Card {
                Layout.fillWidth: true
                implicitHeight: modeCol.implicitHeight + 2 * Theme.space4
                ColumnLayout {
                    id: modeCol
                    anchors.left: parent.left; anchors.right: parent.right
                    spacing: Theme.space3
                    AppText { text: appBackend.tr("Type de masquage", appBackend.language); role: "lead" }
                    SegmentedControl {
                        Layout.fillWidth: true
                        current: imageBackend.mode
                        options: [{ value: "blackout", label: appBackend.tr("Noir", appBackend.language) }, { value: "blur", label: appBackend.tr("Flou", appBackend.language) }, { value: "pixelate", label: appBackend.tr("Mosaïque", appBackend.language) }]
                        onPicked: (v) => imageBackend.setMode(v)
                    }
                    AppCheck {
                        Layout.fillWidth: true
                        text: appBackend.tr("Détection automatique des données", appBackend.language)
                        checked: imageBackend.autoDetect
                        onToggled: imageBackend.setAutoDetect(checked)
                    }
                    AppText {
                        visible: imageBackend.boxes.length > 0
                        text: imageBackend.boxes.length + " " + appBackend.tr("zone(s) tracée(s) à la main", appBackend.language)
                        role: "small"; Layout.fillWidth: true
                    }
                    AppText {
                        visible: !imageBackend.hasImage
                        text: appBackend.tr("Astuce : tracez un rectangle à la souris pour masquer une zone précise. Molette pour zoomer, Espace + glisser pour déplacer.", appBackend.language)
                        role: "small"; Layout.fillWidth: true
                    }
                }
            }

            // --- données détectées
            Card {
                id: dataCard
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 120
                ColumnLayout {
                    anchors.fill: parent
                    spacing: Theme.space2
                    RowLayout {
                        Layout.fillWidth: true
                        AppText { text: imageBackend.textWarning !== "" ? appBackend.tr("Texte NON lu", appBackend.language) : appBackend.tr("Données détectées", appBackend.language)
                                  role: "lead"; Layout.fillWidth: true; color: imageBackend.textWarning !== "" ? Theme.warning : Theme.text }
                        Badge { visible: imageBackend.detected; text: imageBackend.entities.length
                                tone: imageBackend.textWarning !== "" ? "warning" : imageBackend.entities.length ? "info" : "neutral" }
                        AppButton {
                            text: appBackend.tr("Détecter", appBackend.language); variant: "ghost"; implicitHeight: 30
                            enabled: imageBackend.hasImage && !imageBackend.busy
                            onClicked: imageBackend.detect()
                        }
                    }
                    // texte non lu : explication permanente (la notification, elle, disparaît).
                    // Petite fenêtre : seul le titre « Texte NON lu » reste, pour laisser voir la liste.
                    Rectangle {
                        visible: imageBackend.textWarning !== "" && dataCard.height >= 200
                        Layout.fillWidth: true
                        implicitHeight: unreadText.implicitHeight + 2 * Theme.space2
                        radius: Theme.radiusS + 2
                        color: Theme.warningSoft; border.width: 1; border.color: Theme.warning
                        AppText {
                            id: unreadText
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                            anchors.margins: Theme.space2
                            role: "small"; color: Theme.warning
                            maximumLineCount: 6; elide: Text.ElideRight
                            text: appBackend.tr(imageBackend.textWarning, appBackend.language)
                            Accessible.role: Accessible.AlertMessage; Accessible.name: text
                        }
                    }
                    AppText {
                        visible: list.count === 0
                        Layout.fillWidth: true; Layout.fillHeight: true
                        verticalAlignment: Text.AlignVCenter; horizontalAlignment: Text.AlignHCenter
                        role: "small"
                        text: imageBackend.textWarning !== "" ? appBackend.tr("Aucun visage repéré. Le texte, lui, reste à vérifier.", appBackend.language)
                            : imageBackend.detected ? appBackend.tr("Aucune donnée sensible repérée.", appBackend.language) : appBackend.tr("Cliquez sur « Détecter » pour lister les données, puis excluez celles à conserver.", appBackend.language)
                    }
                    ListView {
                        id: list
                        Layout.fillWidth: true; Layout.fillHeight: true
                        visible: count > 0
                        clip: true
                        spacing: 4
                        model: imageBackend.entities
                        ScrollBar.vertical: ScrollBar { }
                        delegate: Rectangle {
                            width: list.width - 8
                            height: 52
                            radius: Theme.radiusS + 2
                            color: imageBackend.selectedEntity === index ? Theme.accentSoft : rowHover.containsMouse ? Theme.surfaceHi : "transparent"
                            border.width: imageBackend.selectedEntity === index ? 1 : 0
                            border.color: Theme.accent
                            Behavior on color { ColorAnimation { duration: Theme.durFast } }
                            opacity: modelData.excluded ? 0.55 : 1
                            MouseArea { id: rowHover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: imageBackend.selectEntity(modelData.id) }
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 4
                                spacing: Theme.space2
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 0
                                    AppText { text: modelData.label; role: "small"; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                                    AppText { text: modelData.value; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap
                                              font.strikeout: modelData.excluded }
                                }
                                IconButton {
                                    iconName: modelData.excluded ? "eye-off" : "check"
                                    active: !modelData.excluded
                                    tip: modelData.excluded ? appBackend.tr("Exclu : cette donnée sera conservée. Cliquer pour la masquer.", appBackend.language) : appBackend.tr("Sera masquée. Cliquer pour l'exclure.", appBackend.language)
                                    size: 32
                                    onClicked: imageBackend.setEntityExcluded(modelData.id, !modelData.excluded)
                                }
                            }
                        }
                    }
                }
            }

            // --- actions
            Badge { visible: imageBackend.stale; text: appBackend.tr("Réglages modifiés : relancez l'anonymisation", appBackend.language); tone: "warning"; Layout.alignment: Qt.AlignHCenter }
            AppButton {
                Layout.fillWidth: true
                implicitHeight: 46
                variant: "primary"
                iconName: "shield"
                text: imageBackend.busy ? appBackend.tr("Traitement…", appBackend.language) : imageBackend.hasResult ? appBackend.tr("Anonymiser à nouveau", appBackend.language) : appBackend.tr("Anonymiser", appBackend.language)
                enabled: imageBackend.hasImage && !imageBackend.busy
                onClicked: imageBackend.anonymize()
            }
            AppButton {
                Layout.fillWidth: true
                text: appBackend.tr("Enregistrer l'image", appBackend.language); iconName: "download"
                enabled: imageBackend.hasResult && !imageBackend.busy
                onClicked: page.saveDialog()
            }
        }
    }

    ConfirmDialog {
        id: clearDlg
        title: appBackend.tr("Effacer toutes les zones ?", appBackend.language)
        message: appBackend.tr("Les zones tracées à la main et les zones détectées par l’OCR seront effacées.", appBackend.language)
        confirmText: appBackend.tr("Effacer", appBackend.language)
        onConfirmed: { page.view = "original"; imageBackend.clearAllZones() }
    }
}
