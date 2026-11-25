import QtQuick
import QtQuick.Layouts

// État vide : médaillon d'icône, titre, explication, et un emplacement pour des boutons.
ColumnLayout {
    id: root
    property string iconName: "image"
    property string title: ""
    property string subtitle: ""
    default property alias actions: actionsRow.data
    spacing: Theme.space3

    Item {
        Layout.alignment: Qt.AlignHCenter
        implicitWidth: 96; implicitHeight: 96
        Rectangle {
            anchors.centerIn: parent; width: 96; height: 96; radius: 48
            color: Theme.accentSoft
            opacity: 0.55
            SequentialAnimation on scale {
                loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 1.08; duration: 1800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 1800; easing.type: Easing.InOutSine }
            }
        }
        Rectangle {
            anchors.centerIn: parent; width: 68; height: 68; radius: 34
            color: Theme.accentSoft
            border.width: 1; border.color: Theme.accent
            Icon { anchors.centerIn: parent; name: root.iconName; size: 30; color: Theme.accentFg }
        }
    }
    AppText { text: root.title; role: "title"; Layout.alignment: Qt.AlignHCenter; horizontalAlignment: Text.AlignHCenter; Layout.maximumWidth: 420; Layout.fillWidth: true }
    AppText { text: root.subtitle; role: "muted"; Layout.alignment: Qt.AlignHCenter; horizontalAlignment: Text.AlignHCenter; Layout.maximumWidth: 420; Layout.fillWidth: true; visible: text !== "" }
    RowLayout { id: actionsRow; Layout.alignment: Qt.AlignHCenter; Layout.topMargin: Theme.space2; spacing: Theme.space3 }
}
