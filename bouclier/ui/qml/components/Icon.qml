import QtQuick
import QtQuick.Effects

// Icône vectorielle (SVG embarqué) recolorée à la volée.
Item {
    id: root
    property string name: ""
    property int size: 20
    property color color: Theme.text
    implicitWidth: size
    implicitHeight: size

    Image {
        id: img
        anchors.fill: parent
        visible: false
        source: root.name ? Qt.resolvedUrl("../../assets/icons/" + root.name + ".svg") : ""
        sourceSize: Qt.size(Math.ceil(root.size * Screen.devicePixelRatio * 2), Math.ceil(root.size * Screen.devicePixelRatio * 2))
        smooth: true
        mipmap: true
    }
    MultiEffect {
        anchors.fill: parent
        source: img
        colorization: 1.0
        colorizationColor: root.color
    }
}
