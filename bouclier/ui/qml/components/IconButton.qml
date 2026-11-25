import QtQuick
import QtQuick.Controls.Basic

AbstractButton {
    id: control
    property string iconName: ""
    property string tip: ""
    property bool active: false
    property int size: 36
    implicitWidth: size
    implicitHeight: size
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: tip
    scale: down ? 0.92 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }
    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 500
    ToolTip.text: tip
    Keys.onReturnPressed: clicked()
    Keys.onSpacePressed: clicked()

    background: Rectangle {
        radius: Theme.radiusS + 2
        color: control.active ? Theme.accentSoft : control.down ? Theme.surfaceTop : control.hovered ? Theme.surfaceHi : "transparent"
        border.width: control.visualFocus ? 2 : 0
        border.color: Theme.accent
        Behavior on color { ColorAnimation { duration: Theme.durFast } }
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: 18
            color: !control.enabled ? Theme.textFaint : control.active ? Theme.accentFg : Theme.text
        }
    }
}
