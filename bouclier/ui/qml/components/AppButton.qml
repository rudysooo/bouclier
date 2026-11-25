import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property string variant: "secondary"   // primary | secondary | ghost | danger
    property string iconName: ""
    property bool busy: false
    implicitHeight: 38
    implicitWidth: Math.max(40, row.implicitWidth + 32)
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    scale: down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: 90; easing.type: Theme.easing } }
    Accessible.name: text
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()

    readonly property color fg: !enabled ? Theme.textFaint
        : variant === "primary" ? Theme.accentText
        : variant === "danger" ? Theme.danger : Theme.text

    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Icon { visible: control.iconName !== ""; name: control.iconName; size: 18; color: control.fg; anchors.verticalCenter: parent.verticalCenter }
            Text {
                visible: control.text !== ""
                text: control.text
                color: control.fg
                font.family: Theme.fontFamily
                font.pixelSize: Theme.fsBody
                font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    background: Rectangle {
        anchors.fill: parent
        radius: Theme.radiusS + 2
        color: {
            if (!control.enabled) return control.variant === "primary" ? Theme.surfaceTop : "transparent"
            if (control.variant === "primary") return control.down ? Theme.accentPress : control.hovered ? Theme.accentHover : Theme.accent
            if (control.variant === "danger") return control.hovered ? Theme.dangerSoft : "transparent"
            if (control.variant === "ghost") return control.down ? Theme.surfaceTop : control.hovered ? Theme.surfaceHi : "transparent"
            return control.down ? Theme.surfaceTop : control.hovered ? Theme.surfaceTop : Theme.surfaceHi
        }
        border.width: control.visualFocus ? 2 : (control.variant === "secondary" || control.variant === "danger" ? 1 : 0)
        border.color: control.visualFocus ? Theme.accent : control.variant === "danger" ? Theme.danger : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.durFast } }
    }
}
