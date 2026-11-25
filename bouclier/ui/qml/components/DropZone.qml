import QtQuick

// Zone de dépôt (glisser-déposer) cliquable. Émet les URLs (file://...) déposées.
Item {
    id: root
    property alias dragging: drop.containsDrag
    signal dropped(var urls)
    signal activated()
    default property alias content: holder.data

    Canvas {
        id: border
        anchors.fill: parent
        property color stroke: drop.containsDrag ? Theme.accent : Theme.borderStrong
        onStrokeChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var ctx = getContext("2d"); ctx.reset()
            var r = Theme.radiusL, w = width - 2, h = height - 2, x = 1, y = 1
            ctx.setLineDash([7, 6]); ctx.lineWidth = drop.containsDrag ? 2.5 : 1.5; ctx.strokeStyle = stroke
            ctx.beginPath()
            ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.arcTo(x + w, y, x + w, y + r, r)
            ctx.lineTo(x + w, y + h - r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r)
            ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r)
            ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r); ctx.closePath(); ctx.stroke()
        }
    }
    Rectangle {
        anchors.fill: parent; anchors.margins: 1; radius: Theme.radiusL
        color: drop.containsDrag ? Theme.accentSoft : (hover.containsMouse ? Theme.surfaceHi : "transparent")
        opacity: drop.containsDrag ? 0.9 : 0.6
        Behavior on color { ColorAnimation { duration: Theme.durMed } }
    }
    Item { id: holder; anchors.fill: parent }
    MouseArea { id: hover; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.activated() }
    DropArea {
        id: drop
        anchors.fill: parent
        onDropped: (d) => { if (d.hasUrls) root.dropped(d.urls) }
    }
    activeFocusOnTab: true
    Keys.onReturnPressed: activated()
    Keys.onSpacePressed: activated()
    Accessible.role: Accessible.Button
    Accessible.name: appBackend.tr("Zone de dépôt de fichiers", appBackend.language)
}
