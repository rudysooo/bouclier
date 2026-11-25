import QtQuick

// Pile de notifications en bas à droite. Appeler show(kind, message).
Item {
    id: root
    anchors.fill: parent
    z: 1000
    function show(kind, message) {
        model.append({ kind: kind, message: message })
        if (model.count > 4) model.remove(0)
    }
    function removeToast(rowIndex) {
        if (rowIndex >= 0 && rowIndex < model.count)
            model.remove(rowIndex)
    }
    ListModel { id: model }
    Column {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.space5
        spacing: Theme.space2
        Repeater {
            model: model
            delegate: Rectangle {
                id: toast
                width: Math.min(420, root.width - 2 * Theme.space5)
                height: row.implicitHeight + 24
                radius: Theme.radiusM
                color: Theme.surfaceTop
                border.width: 1
                border.color: kind === "success" ? Theme.accent : kind === "error" ? Theme.danger : kind === "warning" ? Theme.warning : Theme.info
                opacity: 0
                x: 30
                Component.onCompleted: { opacity = 1; x = 0 }
                Behavior on opacity { NumberAnimation { duration: Theme.durMed } }
                Behavior on x { NumberAnimation { duration: Theme.durSlow; easing.type: Theme.easing } }
                Accessible.role: Accessible.AlertMessage
                Accessible.name: message
                Row {
                    id: row
                    x: 14; anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 28
                    spacing: 12
                    Icon {
                        name: kind === "success" ? "check" : kind === "error" ? "x" : kind === "warning" ? "alert" : "info"
                        color: kind === "success" ? Theme.accentFg : kind === "error" ? Theme.danger : kind === "warning" ? Theme.warning : Theme.info
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    AppText { text: message; width: parent.width - 36; anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea { anchors.fill: parent; onClicked: root.removeToast(index) }
                Timer { interval: kind === "error" ? 8000 : 4200; running: true; onTriggered: { toast.opacity = 0; killer.start() } }
                Timer { id: killer; interval: Theme.durMed; onTriggered: root.removeToast(index) }
            }
        }
    }
}
