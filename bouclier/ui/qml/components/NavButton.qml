import QtQuick
import QtQuick.Controls.Basic

AbstractButton {
    id: control
    property string iconName: ""
    property bool current: false
    width: Theme.railWidth
    height: 56
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text
    Accessible.role: Accessible.PageTab
    ToolTip.visible: hovered
    ToolTip.delay: 400
    ToolTip.text: text
    Keys.onReturnPressed: clicked()
    Keys.onSpacePressed: clicked()
    background: Rectangle {
        anchors.centerIn: parent
        width: 48; height: 44; radius: Theme.radiusM
        color: control.down ? Theme.surfaceTop : control.hovered && !control.current ? Theme.surfaceHi : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.durFast } }
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: 22
            color: control.current ? Theme.accentFg : control.hovered ? Theme.text : Theme.textMuted
            scale: control.down ? 0.88 : control.hovered ? 1.08 : 1
            Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Theme.easing } }
        }
    }
}
