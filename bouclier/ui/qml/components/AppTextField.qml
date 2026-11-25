import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: control
    implicitHeight: 38
    color: Theme.text
    placeholderTextColor: Theme.textFaint
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentText
    font.family: Theme.fontFamily
    font.pixelSize: Theme.fsBody
    leftPadding: 12; rightPadding: 12
    selectByMouse: true
    background: Rectangle {
        radius: Theme.radiusS + 2
        color: Theme.surfaceHi
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.border
        Behavior on border.color { ColorAnimation { duration: Theme.durFast } }
    }
}
