import QtQuick
import QtQuick.Controls.Basic

CheckBox {
    id: control
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    spacing: 10
    implicitHeight: 32
    indicator: Rectangle {
        x: 0; y: (control.height - height) / 2
        width: 20; height: 20; radius: 6
        color: control.checked ? Theme.accent : "transparent"
        border.width: control.visualFocus ? 2 : 1.5
        border.color: control.visualFocus ? Theme.accentFg : control.checked ? Theme.accent : control.hovered ? Theme.textMuted : Theme.borderStrong
        Behavior on color { ColorAnimation { duration: Theme.durFast } }
        Icon {
            anchors.centerIn: parent
            name: "check"; size: 14; color: Theme.accentText
            opacity: control.checked ? 1 : 0
            scale: control.checked ? 1 : 0.5
            Behavior on opacity { NumberAnimation { duration: Theme.durFast } }
            Behavior on scale { NumberAnimation { duration: Theme.durFast; easing.type: Easing.OutBack } }
        }
    }
    contentItem: Text {
        leftPadding: 30
        text: control.text
        color: control.enabled ? Theme.text : Theme.textFaint
        font.family: Theme.fontFamily
        font.pixelSize: Theme.fsBody
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
    }
}
