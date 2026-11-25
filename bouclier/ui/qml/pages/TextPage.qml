import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    property bool highlight: false

    Timer { id: debounce; interval: 250; onTriggered: textBackend.process(src.text) }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 2
                AppText { text: appBackend.tr("Anonymiser un texte", appBackend.language); role: "title" }
                AppText { text: appBackend.tr("Collez un texte : les données personnelles sont repérées et remplacées au fil de la frappe.", appBackend.language); role: "muted" }
            }
            Item { Layout.fillWidth: true }
            AppButton { text: appBackend.tr("Copier le résultat", appBackend.language); iconName: "copy"; variant: "primary"; enabled: textBackend.redacted !== ""; onClicked: textBackend.copyResult() }
        }

        // types de données + style
        Card {
            Layout.fillWidth: true
            implicitHeight: flow.implicitHeight + 2 * Theme.space3 + 8
            padding: Theme.space3
            ColumnLayout {
                anchors.left: parent.left; anchors.right: parent.right
                spacing: Theme.space2
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Theme.space4
                    Flow {
                        id: flow
                        Layout.fillWidth: true
                        spacing: Theme.space4
                        Repeater {
                            model: textBackend.kinds
                            delegate: AppCheck { text: appBackend.tr(modelData.label, appBackend.language); checked: modelData.on; onToggled: textBackend.setKind(modelData.key, checked) }
                        }
                    }
                    SegmentedControl {
                        Layout.preferredWidth: 330
                        current: textBackend.style
                        options: [{ value: "placeholder", label: appBackend.tr("[Étiquette]", appBackend.language) }, { value: "stars", label: appBackend.tr("••• Étoiles", appBackend.language) }, { value: "pseudonym", label: appBackend.tr("Pseudonyme", appBackend.language) }]
                        onPicked: (v) => textBackend.setStyle(v)
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.space4

            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1
                spacing: Theme.space2
                RowLayout {
                    AppText { text: appBackend.tr("Texte d'origine", appBackend.language); role: "lead"; Layout.fillWidth: true }
                    Badge { visible: textBackend.count > 0; text: textBackend.count + " " + appBackend.tr("donnée(s) repérée(s)", appBackend.language); tone: "info" }
                    AppButton { text: page.highlight ? appBackend.tr("Modifier", appBackend.language) : appBackend.tr("Surligner", appBackend.language); iconName: page.highlight ? "text" : "eye-off"; variant: "ghost"; implicitHeight: 30
                                enabled: textBackend.count > 0 || page.highlight; onClicked: page.highlight = !page.highlight }
                }
                Item {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    AppTextArea {
                        id: src
                        anchors.fill: parent
                        visible: !page.highlight
                        placeholderText: appBackend.tr("Collez ici un texte contenant des noms, adresses, e-mails, téléphones, IBAN…", appBackend.language)
                        onEdited: debounce.restart()
                    }
                    Rectangle {
                        anchors.fill: parent; visible: page.highlight
                        color: Theme.surfaceHi; radius: Theme.radiusM; border.width: 1; border.color: Theme.border
                        ScrollView {
                            anchors.fill: parent; anchors.margins: 2; clip: true
                            TextArea {
                                readOnly: true; selectByMouse: true; textFormat: TextEdit.RichText
                                text: textBackend.sourceHtml; wrapMode: TextEdit.Wrap
                                color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBody
                                leftPadding: 14; rightPadding: 14; topPadding: 12; bottomPadding: 12; background: null
                            }
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1
                spacing: Theme.space2
                AppText { text: appBackend.tr("Résultat anonymisé", appBackend.language); role: "lead" }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    color: Theme.surfaceHi; radius: Theme.radiusM; border.width: 1; border.color: Theme.border
                    ScrollView {
                        anchors.fill: parent; anchors.margins: 2; clip: true
                        TextArea {
                            readOnly: true; selectByMouse: true; textFormat: TextEdit.RichText
                            text: textBackend.resultHtml; wrapMode: TextEdit.Wrap
                            placeholderText: appBackend.tr("Le texte anonymisé apparaîtra ici.", appBackend.language)
                            placeholderTextColor: Theme.textFaint
                            color: Theme.text; font.family: Theme.fontFamily; font.pixelSize: Theme.fsBody
                            leftPadding: 14; rightPadding: 14; topPadding: 12; bottomPadding: 12; background: null
                        }
                    }
                }
            }
        }
    }
}
