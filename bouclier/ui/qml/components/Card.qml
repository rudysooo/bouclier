import QtQuick
import QtQuick.Effects

// Carte : surface arrondie, bordure fine, ombre douce.
Item {
    id: root
    property int padding: Theme.space4
    property bool elevated: true
    property color fill: Theme.surface
    property alias radius: bg.radius
    default property alias content: inner.data

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: Theme.radiusL
        color: root.fill
        border.width: 1
        border.color: Theme.border
        visible: !root.elevated
        Behavior on color { ColorAnimation { duration: Theme.durMed } }
    }
    Rectangle {
        id: bgSrc
        anchors.fill: parent
        radius: bg.radius
        color: root.fill
        border.width: 1
        border.color: Theme.border
        visible: false
        layer.enabled: root.elevated
    }
    MultiEffect {
        anchors.fill: bgSrc
        source: bgSrc
        visible: root.elevated
        shadowEnabled: true
        shadowColor: Theme.shadow
        shadowBlur: 0.7
        shadowVerticalOffset: 6
        autoPaddingEnabled: true
    }
    Item {
        id: inner
        anchors.fill: parent
        anchors.margins: root.padding
    }
}
