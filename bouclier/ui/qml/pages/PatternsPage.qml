import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property string pendingDelete: ""
    property bool pendingIsKeyword: false
    property var testResult: ({ valid: true, error: "", count: 0, html: "" })
    function runTest() { page.testResult = patternsBackend.testPattern(rx.text, sample.text) }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        ColumnLayout {
            spacing: 2
            AppText { text: appBackend.tr("Motifs & mots-clés", appBackend.language); role: "title" }
            AppText { text: appBackend.tr("Vos propres règles de masquage, appliquées aux textes et aux images. Enregistrées localement.", appBackend.language); role: "muted" }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            spacing: Theme.space4

            // --- motifs (regex)
            Card {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1
                ColumnLayout {
                    anchors.fill: parent; spacing: Theme.space3
                    AppText { text: appBackend.tr("Motifs (expressions régulières)", appBackend.language); role: "lead" }
                    RowLayout {
                        spacing: Theme.space2
                        AppTextField { id: lbl; Layout.preferredWidth: 130; placeholderText: appBackend.tr("Nom (ex. Dossier)", appBackend.language); Accessible.name: appBackend.tr("Nom du motif", appBackend.language) }
                        AppTextField { id: rx; Layout.fillWidth: true; placeholderText: appBackend.tr("Motif (ex. DOS-\\d{4})", appBackend.language); Accessible.name: appBackend.tr("Expression régulière", appBackend.language)
                                       font.family: "Consolas, Menlo, monospace"; onTextChanged: page.runTest(); onAccepted: addBtn.clicked() }
                        AppButton { id: addBtn; text: appBackend.tr("Ajouter", appBackend.language); iconName: "plus"; variant: "primary"
                                    enabled: lbl.text.trim() !== "" && rx.text.trim() !== "" && page.testResult.valid
                                    onClicked: { patternsBackend.addPattern(lbl.text, rx.text); if (page.testResult.valid) { lbl.text = ""; } } }
                    }
                    AppText { visible: !page.testResult.valid; text: page.testResult.error; color: Theme.danger; role: "small"; Layout.fillWidth: true }

                    AppText { text: appBackend.tr("Test en direct", appBackend.language); role: "small" }
                    AppTextArea {
                        id: sample
                        Layout.fillWidth: true; Layout.preferredHeight: 84
                        placeholderText: appBackend.tr("Écrivez un texte d'exemple pour voir ce que le motif détecte…", appBackend.language)
                        onEdited: page.runTest()
                    }
                    Rectangle {
                        Layout.fillWidth: true; Layout.preferredHeight: 84
                        color: Theme.surfaceHi; radius: Theme.radiusM; border.width: 1; border.color: Theme.border
                        visible: sample.text !== ""
                        ScrollView {
                            anchors.fill: parent; anchors.margins: 2; clip: true
                            TextArea {
                                readOnly: true; textFormat: TextEdit.RichText; wrapMode: TextEdit.Wrap; background: null
                                text: page.testResult.html; color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBody
                                leftPadding: 14; topPadding: 10
                            }
                        }
                    }
                    AppText { visible: sample.text !== "" && rx.text !== "" && page.testResult.valid
                              text: page.testResult.count + " " + appBackend.tr("correspondance(s) dans l'exemple", appBackend.language); role: "small" }

                    AppText { text: appBackend.tr("Motifs enregistrés", appBackend.language); role: "small" }
                    ListView {
                        id: pats
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; spacing: 4
                        model: patternsBackend.patterns
                        ScrollBar.vertical: ScrollBar { }
                        delegate: Rectangle {
                            width: pats.width - 8; height: 48; radius: Theme.radiusS + 2; color: Theme.surfaceHi
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 4
                                ColumnLayout {
                                    Layout.fillWidth: true; spacing: 0
                                    AppText { text: modelData.label; font.weight: Font.Medium; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                                    AppText { text: modelData.regex; role: "small"; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap; font.family: "Consolas, Menlo, monospace" }
                                }
                                IconButton { iconName: "trash"; tip: appBackend.tr("Supprimer ce motif", appBackend.language); size: 32
                                             onClicked: { page.pendingDelete = modelData.id; page.pendingIsKeyword = false; confirm.open() } }
                            }
                        }
                        AppText { anchors.centerIn: parent; visible: pats.count === 0; text: appBackend.tr("Aucun motif personnalisé.", appBackend.language); role: "small" }
                    }
                }
            }

            // --- mots-clés
            Card {
                Layout.preferredWidth: 340; Layout.maximumWidth: 340; Layout.fillHeight: true
                ColumnLayout {
                    anchors.fill: parent; spacing: Theme.space3
                    AppText { text: appBackend.tr("Mots-clés", appBackend.language); role: "lead" }
                    AppText { text: appBackend.tr("Un mot ou une expression à toujours masquer (sans tenir compte des majuscules).", appBackend.language); role: "small"; Layout.fillWidth: true }
                    RowLayout {
                        spacing: Theme.space2
                        AppTextField { id: kw; Layout.fillWidth: true; placeholderText: appBackend.tr("Ex. Projet Phoenix", appBackend.language); Accessible.name: appBackend.tr("Nouveau mot-clé", appBackend.language)
                                       onAccepted: kwBtn.clicked() }
                        AppButton { id: kwBtn; text: appBackend.tr("Ajouter", appBackend.language); variant: "primary"; enabled: kw.text.trim().length >= 2
                                    onClicked: { patternsBackend.addKeyword(kw.text); kw.text = "" } }
                    }
                    ListView {
                        id: kws
                        Layout.fillWidth: true; Layout.fillHeight: true
                        clip: true; spacing: 4
                        model: patternsBackend.keywords
                        ScrollBar.vertical: ScrollBar { }
                        delegate: Rectangle {
                            width: kws.width - 8; height: 40; radius: Theme.radiusS + 2; color: Theme.surfaceHi
                            RowLayout {
                                anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 4
                                AppText { text: modelData; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
                                IconButton { iconName: "x"; tip: appBackend.tr("Supprimer ce mot-clé", appBackend.language); size: 30
                                             onClicked: { page.pendingDelete = modelData; page.pendingIsKeyword = true; confirm.open() } }
                            }
                        }
                        AppText { anchors.centerIn: parent; visible: kws.count === 0; text: appBackend.tr("Aucun mot-clé.", appBackend.language); role: "small" }
                    }
                }
            }
        }
    }

    ConfirmDialog {
        id: confirm
        title: page.pendingIsKeyword ? appBackend.tr("Supprimer ce mot-clé ?", appBackend.language) : appBackend.tr("Supprimer ce motif ?", appBackend.language)
        message: appBackend.tr("Il ne sera plus masqué dans vos textes et vos images.", appBackend.language)
        confirmText: appBackend.tr("Supprimer", appBackend.language)
        onConfirmed: page.pendingIsKeyword ? patternsBackend.removeKeyword(page.pendingDelete) : patternsBackend.removePattern(page.pendingDelete)
    }
}
