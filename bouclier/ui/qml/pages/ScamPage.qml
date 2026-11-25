import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"

Item {
    id: page
    // 0..100 animé
    property real shown: 0
    Behavior on shown { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
    Connections {
        target: scamBackend
        function onChanged() { page.shown = scamBackend.analyzed ? scamBackend.score : 0 }
    }
    readonly property color levelColor: scamBackend.level === "critical" ? Theme.danger : scamBackend.level === "high" ? Theme.warning : Theme.accent

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.space5
        spacing: Theme.space4

        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1
            spacing: Theme.space3
            ColumnLayout {
                spacing: 2
                AppText { text: appBackend.tr("Anti-arnaque", appBackend.language); role: "title" }
                AppText { text: appBackend.tr("Collez un SMS, un e-mail ou un message reçu : Bouclier cherche les signaux typiques du phishing. Rien ne quitte votre ordinateur.", appBackend.language)
                          role: "muted"; Layout.fillWidth: true }
            }
            AppTextArea {
                id: msg
                Layout.fillWidth: true; Layout.fillHeight: true
                placeholderText: appBackend.tr("Collez ici le message suspect…", appBackend.language)
            }
            RowLayout {
                spacing: Theme.space2
                AppButton { text: appBackend.tr("Analyser le message", appBackend.language); iconName: "shield"; variant: "primary"; enabled: msg.text.trim() !== ""; onClicked: scamBackend.analyze(msg.text) }
                AppButton { text: appBackend.tr("Effacer", appBackend.language); variant: "ghost"; onClicked: { msg.text = ""; scamBackend.reset() } }
            }
        }

        Card {
            Layout.preferredWidth: 380; Layout.maximumWidth: 380; Layout.fillHeight: true
            padding: Theme.space5

            // état vide
            EmptyState {
                anchors.centerIn: parent
                width: parent.width
                visible: !scamBackend.analyzed
                iconName: "alert"
                title: appBackend.tr("En attente d'un message", appBackend.language)
                subtitle: appBackend.tr("Le niveau de risque, les raisons et les conseils s'afficheront ici.", appBackend.language)
            }

            Flickable {
              id: scroll
              anchors.fill: parent
              visible: scamBackend.analyzed
              clip: true
              contentWidth: width
              contentHeight: results.implicitHeight
              boundsBehavior: Flickable.StopAtBounds
              ScrollBar.vertical: ScrollBar { }
              Connections { target: scamBackend; function onChanged() { scroll.contentY = 0 } }

              ColumnLayout {
                id: results
                width: scroll.width - 12
                spacing: Theme.space4

                Item {
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: 220; implicitHeight: 150
                    Canvas {
                        id: gauge
                        anchors.fill: parent
                        property real v: page.shown
                        property color col: page.levelColor
                        property color track: Theme.surfaceTop
                        onVChanged: requestPaint()
                        onColChanged: requestPaint()
                        onTrackChanged: requestPaint()
                        onPaint: {
                            var ctx = getContext("2d"); ctx.reset()
                            var cx = width / 2, cy = height - 16, r = 90
                            ctx.lineWidth = 16; ctx.lineCap = "round"
                            ctx.strokeStyle = track
                            ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI); ctx.stroke()
                            if (v > 0.5) {
                                ctx.strokeStyle = col
                                ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, Math.PI + Math.PI * Math.min(v, 100) / 100); ctx.stroke()
                            }
                        }
                    }
                    Column {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 60
                        AppText { text: Math.round(page.shown); role: "hero"; font.pixelSize: 44; anchors.horizontalCenter: parent.horizontalCenter; color: page.levelColor }
                        AppText { text: appBackend.tr("sur 100", appBackend.language); role: "small"; anchors.horizontalCenter: parent.horizontalCenter }
                    }
                }
                AppText { text: appBackend.tr(scamBackend.label, appBackend.language); role: "title"; Layout.alignment: Qt.AlignHCenter; color: page.levelColor }

                AppText { text: appBackend.tr("Pourquoi", appBackend.language); role: "lead"; visible: scamBackend.reasons.length > 0 }
                Repeater {
                    model: scamBackend.reasons
                    delegate: RowLayout {
                        Layout.fillWidth: true; spacing: Theme.space2
                        Icon { name: "alert"; size: 16; color: Theme.warning; Layout.alignment: Qt.AlignTop }
                        AppText { text: appBackend.tr(modelData.text, appBackend.language); Layout.fillWidth: true }
                        Badge { text: "+" + modelData.weight; tone: "warning" }
                    }
                }
                AppText { text: appBackend.tr("Aucun signal d'arnaque connu repéré. Restez prudent : l'analyse est locale et limitée.", appBackend.language)
                          role: "muted"; visible: scamBackend.reasons.length === 0; Layout.fillWidth: true }

                AppText { text: appBackend.tr("Nos conseils", appBackend.language); role: "lead" }
                Repeater {
                    model: scamBackend.advice
                    delegate: RowLayout {
                        Layout.fillWidth: true; spacing: Theme.space2
                        Icon { name: "check"; size: 16; color: Theme.accentFg; Layout.alignment: Qt.AlignTop }
                        AppText { text: appBackend.tr(modelData, appBackend.language); Layout.fillWidth: true }
                    }
                }
              }
            }
        }
    }
}
