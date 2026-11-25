import QtQuick
import QtQuick.Controls.Basic

Rectangle {
    id: root
    property alias text: area.text
    property alias placeholderText: area.placeholderText
    property alias readOnly: area.readOnly
    property alias textFormat: area.textFormat
    property alias area: area
    property bool mono: false
    signal edited()
    color: Theme.surfaceHi
    radius: Theme.radiusM
    border.width: area.activeFocus ? 2 : 1
    border.color: area.activeFocus ? Theme.accent : Theme.border
    Behavior on border.color { ColorAnimation { duration: Theme.durFast } }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 2
        clip: true
        TextArea {
            id: area
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            color: Theme.text
            selectionColor: Theme.accent
            selectedTextColor: Theme.accentText
            placeholderTextColor: Theme.textFaint
            font.family: root.mono ? "Consolas, Menlo, monospace" : Theme.fontFamily
            font.pixelSize: Theme.fsBody
            leftPadding: 14; rightPadding: 14; topPadding: 12; bottomPadding: 12
            background: null
            onTextChanged: if (activeFocus) root.edited()
        }
    }
}
