import QtQuick
import QtQuick.Layouts

// options : [{value, label, icon?}] ; current : valeur sélectionnée.
Rectangle {
    id: root
    property var options: []
    property string current: ""
    signal picked(string value)
    implicitHeight: 40
    implicitWidth: Math.max(160, options.length * 96)
    radius: Theme.radiusS + 2
    color: Theme.surfaceHi
    border.width: 1
    border.color: Theme.border

    readonly property int index: { for (var i = 0; i < options.length; ++i) if (options[i].value === current) return i; return 0 }

    Rectangle {
        id: pill
        y: 3; height: parent.height - 6
        width: root.options.length ? (root.width - 6) / root.options.length : 0
        x: 3 + root.index * width
        radius: Theme.radiusS
        color: Theme.accent
        Behavior on x { NumberAnimation { duration: Theme.durMed; easing.type: Theme.easing } }
    }
    Row {
        anchors.fill: parent
        anchors.margins: 3
        Repeater {
            model: root.options
            delegate: Item {
                width: (root.width - 6) / root.options.length
                height: root.height - 6
                activeFocusOnTab: true
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.label
                Keys.onReturnPressed: root.picked(modelData.value)
                Keys.onSpacePressed: root.picked(modelData.value)
                Rectangle { anchors.fill: parent; radius: Theme.radiusS; color: "transparent"; border.width: parent.activeFocus ? 2 : 0; border.color: Theme.accentFg }
                Row {
                    anchors.centerIn: parent
                    spacing: 6
                    Icon { visible: !!modelData.icon; name: modelData.icon || ""; size: 16; anchors.verticalCenter: parent.verticalCenter
                           color: root.current === modelData.value ? Theme.accentText : Theme.textMuted }
                    Text {
                        text: modelData.label
                        font.family: Theme.fontFamily; font.pixelSize: Theme.fsBody; font.weight: Font.Medium
                        color: root.current === modelData.value ? Theme.accentText : Theme.textMuted
                        anchors.verticalCenter: parent.verticalCenter
                        Behavior on color { ColorAnimation { duration: Theme.durFast } }
                    }
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.picked(modelData.value) }
            }
        }
    }
}
