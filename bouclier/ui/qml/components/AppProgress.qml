import QtQuick

Rectangle {
    id: root
    property real value: 0
    property bool indeterminate: false
    implicitHeight: 6
    radius: 3
    color: Theme.surfaceTop
    clip: true
    Accessible.role: Accessible.ProgressBar

    Rectangle {
        id: bar
        height: parent.height
        radius: 3
        color: Theme.accent
        width: root.indeterminate ? parent.width * 0.32 : parent.width * Math.max(0, Math.min(1, root.value))
        x: 0
        Behavior on width { enabled: !root.indeterminate; NumberAnimation { duration: Theme.durMed; easing.type: Theme.easing } }
        SequentialAnimation on x {
            running: root.indeterminate && root.visible
            loops: Animation.Infinite
            NumberAnimation { from: -bar.width; to: root.width; duration: 1100; easing.type: Easing.InOutQuad }
        }
    }
}
