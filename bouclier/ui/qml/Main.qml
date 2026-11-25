import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import "pages"

ApplicationWindow {
    id: win
    width: 1280; height: 800
    minimumWidth: 900; minimumHeight: 600
    visible: true
    title: appBackend.tr("Bouclier", appBackend.language)
    color: Theme.bg
    property int current: 0

    Binding { target: Theme; property: "dark"; value: appBackend.theme !== "light" }
    Behavior on color { ColorAnimation { duration: Theme.durSlow } }

    readonly property var nav: [
        { icon: "image", label: appBackend.tr("Images", appBackend.language) },
        { icon: "text", label: appBackend.tr("Texte", appBackend.language) },
        { icon: "broom", label: appBackend.tr("Nettoyeur de fichiers", appBackend.language) },
        { icon: "alert", label: appBackend.tr("Anti-arnaque", appBackend.language) },
        { icon: "tag", label: appBackend.tr("Motifs et mots-clés", appBackend.language) },
        { icon: "settings", label: appBackend.tr("Paramètres", appBackend.language) }
    ]

    Connections { target: appBackend; function onToast(kind, message) { toasts.show(kind, message) } }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ================================================= barre latérale
        Rectangle {
            Layout.preferredWidth: Theme.railWidth
            Layout.fillHeight: true
            color: Theme.surface
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.border }

            Image {
                id: logo
                source: Qt.resolvedUrl("../assets/logo.svg")
                sourceSize: Qt.size(96, 96)
                width: 38; height: 38
                anchors.horizontalCenter: parent.horizontalCenter
                y: 18
            }
            Item {
                id: rail
                y: 80
                width: parent.width
                height: 6 * 56

                // indicateur animé
                Rectangle {
                    id: indicator
                    x: 0; width: 4; height: 24; radius: 2
                    y: win.current === 5 ? 0 : win.current * 56 + 16
                    visible: win.current !== 5
                    color: Theme.accent
                    Behavior on y { NumberAnimation { duration: Theme.durMed; easing.type: Theme.easing } }
                }
                Column {
                    Repeater {
                        model: 5
                        delegate: NavButton {
                            iconName: win.nav[index].icon
                            text: win.nav[index].label
                            current: win.current === index
                            onClicked: win.current = index
                        }
                    }
                }
            }
            // paramètres en bas
            NavButton {
                anchors.bottom: parent.bottom; anchors.bottomMargin: 14
                iconName: "settings"; text: appBackend.tr("Paramètres", appBackend.language)
                current: win.current === 5
                onClicked: win.current = 5
                Rectangle { visible: win.current === 5; x: 0; anchors.verticalCenter: parent.verticalCenter; width: 4; height: 24; radius: 2; color: Theme.accent }
            }
        }

        // ================================================= pages
        StackLayout {
            id: stack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: win.current

            ImagesPage { id: imagesPage }
            TextPage { }
            CleanerPage { id: cleanerPage }
            ScamPage { }
            PatternsPage { }
            SettingsPage { }
        }
    }

    // transition douce entre pages
    onCurrentChanged: { fade.restart() }
    Rectangle {
        id: veil
        x: Theme.railWidth; width: parent.width - Theme.railWidth; height: parent.height
        color: Theme.bg; opacity: 0; enabled: false
        NumberAnimation on opacity { id: fade; from: 0.85; to: 0; duration: Theme.durMed; easing.type: Theme.easing; running: false }
    }

    // ================================================= raccourcis
    Shortcut { sequences: [StandardKey.Open]; onActivated: { if (win.current === 0) imagesPage.openDialog(); else if (win.current === 2) cleanerPage.openDialog() } }
    Shortcut { sequences: [StandardKey.Save]; enabled: win.current === 0; onActivated: imagesPage.saveDialog() }
    Shortcut { sequence: "Ctrl+Z"; enabled: win.current === 0; onActivated: imagesPage.undo() }
    Shortcut { sequences: ["Ctrl+Shift+Z", "Ctrl+Y"]; enabled: win.current === 0; onActivated: imagesPage.redo() }
    Shortcut { sequence: "Ctrl+1"; onActivated: win.current = 0 }
    Shortcut { sequence: "Ctrl+2"; onActivated: win.current = 1 }
    Shortcut { sequence: "Ctrl+3"; onActivated: win.current = 2 }
    Shortcut { sequence: "Ctrl+4"; onActivated: win.current = 3 }
    Shortcut { sequence: "Ctrl+5"; onActivated: win.current = 4 }
    Shortcut { sequence: "Ctrl+,"; onActivated: win.current = 5 }

    ToastHost { id: toasts }

    // Écran d'accueil affiché dès que la fenêtre Qt existe, puis retiré en fondu.
    Rectangle {
        id: startupCover
        anchors.fill: parent
        z: 10000
        color: Theme.bg
        opacity: 1
        visible: opacity > 0
        Column {
            anchors.centerIn: parent
            spacing: 18
            Image { source: Qt.resolvedUrl("../assets/logo.svg"); width: 76; height: 76; sourceSize: Qt.size(152, 152); anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: appBackend.tr("BOUCLIER", appBackend.language); color: Theme.text; font.pixelSize: 24; font.weight: Font.DemiBold; anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: appBackend.tr("Préparation de votre espace sécurisé…", appBackend.language); color: Theme.textMuted; font.pixelSize: 13; anchors.horizontalCenter: parent.horizontalCenter }
            Rectangle {
                width: 180; height: 3; radius: 2; color: Theme.border; anchors.horizontalCenter: parent.horizontalCenter
                Rectangle { height: parent.height; width: parent.width * 0.42; radius: 2; color: Theme.accent
                    NumberAnimation on x { from: 0; to: 180 * 0.58; duration: 900; loops: Animation.Infinite }
                }
            }
        }
        Timer { interval: 900; running: true; onTriggered: startupFade.start() }
        NumberAnimation { id: startupFade; target: startupCover; property: "opacity"; from: 1; to: 0; duration: 420; easing.type: Easing.OutCubic; onFinished: startupCover.visible = false }
    }
}
