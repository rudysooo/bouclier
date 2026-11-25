import QtQuick
import QtQuick.Controls.Basic

// Aperçu zoomable/déplaçable + zones de masquage (rectangles) + comparaison avant/après.
// Toutes les coordonnées échangées avec le backend sont en PIXELS IMAGE.
Item {
    id: root
    clip: true

    property url source
    property url resultSource
    property int imgW: 0
    property int imgH: 0
    property var boxes: []              // [{x0,y0,x1,y1}] zones manuelles
    property var entities: []           // [{id,label,value,boxes:[[x0,y0,x1,y1]],excluded}]
    property int selectedEntity: -1
    property bool showResult: false     // true : afficher le résultat
    property bool compare: false        // true : curseur avant/après (nécessite resultSource)
    property real split: 0.5
    property bool panTool: false        // outil « main » (sinon : tracer des zones)
    property int selectedBox: -1

    signal boxAdded(real x0, real y0, real x1, real y1)
    signal boxCommitted(int index, real x0, real y0, real x1, real y1)
    signal boxRemoved(int index)

    // --- vue
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property real fitScale: 1
    property bool autoFit: true
    readonly property real inv: 1 / Math.max(zoom, 0.0001)
    property bool spaceDown: false

    function fit() {
        if (imgW <= 0 || imgH <= 0 || width <= 0 || height <= 0) return
        fitScale = Math.min((width - 48) / imgW, (height - 48) / imgH)
        zoom = fitScale
        panX = (width - imgW * zoom) / 2
        panY = (height - imgH * zoom) / 2
        autoFit = true
    }
    function zoomAt(px, py, factor) {
        var nz = Math.max(fitScale * 0.15, Math.min(48, zoom * factor))
        var k = nz / zoom
        panX = px - (px - panX) * k
        panY = py - (py - panY) * k
        zoom = nz
        autoFit = false
    }
    function centerOn(x0, y0, x1, y1) {
        var cx = (x0 + x1) / 2, cy = (y0 + y1) / 2
        var vx = cx * zoom + panX, vy = cy * zoom + panY
        if (vx < 40 || vy < 40 || vx > width - 40 || vy > height - 40) {
            panX = width / 2 - cx * zoom
            panY = height / 2 - cy * zoom
            autoFit = false
        }
    }
    onWidthChanged: if (autoFit) fit()
    onHeightChanged: if (autoFit) fit()
    onImgWChanged: fit()
    onImgHChanged: fit()
    onSourceChanged: { selectedBox = -1; split = 0.5; fit() }
    onSelectedEntityChanged: {
        if (selectedEntity >= 0 && selectedEntity < entities.length && entities[selectedEntity].boxes.length) {
            var b = entities[selectedEntity].boxes[0]
            centerOn(b[0], b[1], b[2], b[3])
        }
    }

    // --- modèle local des zones (évite de recréer les delegates pendant un glisser)
    ListModel { id: boxModel }
    function syncBoxes() {
        var list = root.boxes || []
        if (boxModel.count === list.length) {
            for (var i = 0; i < list.length; ++i) boxModel.set(i, list[i])
        } else {
            boxModel.clear()
            for (var j = 0; j < list.length; ++j) boxModel.append(list[j])
            if (selectedBox >= list.length) selectedBox = -1
        }
    }
    onBoxesChanged: syncBoxes()
    Component.onCompleted: syncBoxes()

    focus: true
    activeFocusOnTab: true
    Keys.onPressed: (e) => {
        if (e.key === Qt.Key_Space && !e.isAutoRepeat) { spaceDown = true; e.accepted = true }
        else if ((e.key === Qt.Key_Delete || e.key === Qt.Key_Backspace) && selectedBox >= 0) { root.boxRemoved(selectedBox); selectedBox = -1; e.accepted = true }
        else if (e.key === Qt.Key_Plus || e.key === Qt.Key_Equal) { zoomAt(width / 2, height / 2, 1.25); e.accepted = true }
        else if (e.key === Qt.Key_Minus) { zoomAt(width / 2, height / 2, 1 / 1.25); e.accepted = true }
        else if (e.key === Qt.Key_0) { fit(); e.accepted = true }
    }
    Keys.onReleased: (e) => { if (e.key === Qt.Key_Space && !e.isAutoRepeat) { spaceDown = false; e.accepted = true } }
    Accessible.role: Accessible.Graphic
    Accessible.name: appBackend.tr("Aperçu de l'image. Molette pour zoomer, glisser pour tracer une zone, espace pour déplacer.", appBackend.language)

    // damier de fond (transparence)
    Rectangle { anchors.fill: parent; color: Theme.dark ? "#070a12" : "#e6ebf5" }

    // =============================================================== scène (coordonnées image)
    Item {
        id: stage
        z: 1
        x: root.panX; y: root.panY
        width: root.imgW; height: root.imgH
        scale: root.zoom
        transformOrigin: Item.TopLeft

        Image {
            id: before
            anchors.fill: parent
            source: root.source
            asynchronous: true
            cache: false
            smooth: root.zoom < 3
            mipmap: root.zoom < 1
            visible: !(root.showResult && !root.compare)
        }
        Image {
            id: afterFull
            anchors.fill: parent
            source: root.resultSource
            asynchronous: true
            cache: false
            smooth: root.zoom < 3
            mipmap: root.zoom < 1
            visible: root.showResult && !root.compare
        }
        // comparaison : « après » à droite du curseur
        Item {
            visible: root.showResult && root.compare
            x: root.split * root.imgW
            width: root.imgW * (1 - root.split)
            height: root.imgH
            clip: true
            Image {
                x: -parent.x
                width: root.imgW; height: root.imgH
                source: root.resultSource
                asynchronous: true; cache: false
                smooth: root.zoom < 3
            }
        }
        Rectangle {
            visible: root.showResult && root.compare
            x: root.split * root.imgW - width / 2
            width: 3 * root.inv; height: root.imgH
            color: Theme.accent
        }

        // Interactions sur la surface image, sous les rectangles sélectionnables
    MouseArea {
        id: area
        anchors.fill: parent
        z: 0
        acceptedButtons: Qt.AllButtons
        hoverEnabled: true
        cursorShape: (root.panTool || root.spaceDown) ? (pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.CrossCursor
        property string mode: ""
        property real sx; property real sy; property real px0; property real py0

        function toImg(mx, my) { return area.mapToItem(stage, mx, my) }
        function clampX(v) { return Math.max(0, Math.min(root.imgW, v)) }
        function clampY(v) { return Math.max(0, Math.min(root.imgH, v)) }

        onPressed: (m) => {
            root.forceActiveFocus()
            if (root.imgW <= 0) return
            root.selectedBox = -1
            var panning = m.button !== Qt.LeftButton || root.panTool || root.spaceDown
            if (panning) { mode = "pan"; sx = m.x; sy = m.y; px0 = root.panX; py0 = root.panY; return }
            mode = "draw"
            var p = toImg(m.x, m.y)
            sx = clampX(p.x); sy = clampY(p.y)
            draft.x = sx; draft.y = sy; draft.width = 0; draft.height = 0; draft.visible = true
        }
        onPositionChanged: (m) => {
            if (!pressed) return
            if (mode === "pan") {
                root.panX = px0 + (m.x - sx) * root.zoom; root.panY = py0 + (m.y - sy) * root.zoom; root.autoFit = false
            } else if (mode === "draw") {
                var p = toImg(m.x, m.y), ex = clampX(p.x), ey = clampY(p.y)
                draft.x = Math.min(sx, ex); draft.y = Math.min(sy, ey)
                draft.width = Math.abs(ex - sx); draft.height = Math.abs(ey - sy)
            }
        }
        onReleased: (m) => {
            if (mode === "draw") {
                draft.visible = false
                if (draft.width * root.zoom >= 6 && draft.height * root.zoom >= 6)
                    root.boxAdded(draft.x, draft.y, draft.x + draft.width, draft.y + draft.height)
            }
            mode = ""
        }
        onWheel: (w) => {
            if (root.imgW <= 0) return
            root.zoomAt(root.panX + w.x * root.zoom, root.panY + w.y * root.zoom, w.angleDelta.y > 0 ? 1.15 : 1 / 1.15)
        }
        onDoubleClicked: root.fit()
    }


        // --- entités détectées (surbrillance)
        Repeater {
            model: root.entities
            delegate: Item {
                property var ent: modelData
                property bool sel: index === root.selectedEntity
                Repeater {
                    model: ent.boxes
                    delegate: Rectangle {
                        x: modelData[0]; y: modelData[1]
                        width: modelData[2] - modelData[0]; height: modelData[3] - modelData[1]
                        color: ent.excluded ? "transparent" : sel ? "#55fbbf24" : "#4438bdf8"
                        border.width: (sel ? 3 : 2) * root.inv
                        border.color: ent.excluded ? Theme.textFaint : sel ? Theme.warning : Theme.info
                        visible: !(root.showResult && !root.compare)
                        opacity: ent.excluded ? 0.6 : 1
                    }
                }
            }
        }

        // --- zones manuelles
        Repeater {
            model: boxModel
            delegate: Item {
                z: 2
                id: bx
                property int bi: index
                property bool selected: root.selectedBox === index
                x: model.x0; y: model.y0
                width: Math.max(1, model.x1 - model.x0); height: Math.max(1, model.y1 - model.y0)
                visible: !(root.showResult && !root.compare)

                Rectangle {
                    anchors.fill: parent
                    color: selected ? "#6610b981" : "#4410b981"
                    border.width: 2 * root.inv
                    border.color: Theme.accent
                }
                // déplacement
                MouseArea {
                    anchors.fill: parent
                    enabled: !(root.panTool || root.spaceDown)
                    cursorShape: Qt.SizeAllCursor
                    property real sx; property real sy; property var orig
                    onPressed: (m) => {
                        root.selectedBox = bx.bi; root.forceActiveFocus()
                        var p = mapToItem(stage, m.x, m.y); sx = p.x; sy = p.y
                        var g = boxModel.get(bx.bi); orig = { x0: g.x0, y0: g.y0, x1: g.x1, y1: g.y1 }
                    }
                    onPositionChanged: (m) => {
                        if (!pressed) return
                        var p = mapToItem(stage, m.x, m.y)
                        var dx = Math.max(-orig.x0, Math.min(root.imgW - orig.x1, p.x - sx))
                        var dy = Math.max(-orig.y0, Math.min(root.imgH - orig.y1, p.y - sy))
                        boxModel.set(bx.bi, { x0: orig.x0 + dx, y0: orig.y0 + dy, x1: orig.x1 + dx, y1: orig.y1 + dy })
                    }
                    onReleased: root.boxCommitted(bx.bi, boxModel.get(bx.bi).x0, boxModel.get(bx.bi).y0, boxModel.get(bx.bi).x1, boxModel.get(bx.bi).y1)
                }
                // poignées de redimensionnement (4 coins)
                Repeater {
                    model: bx.selected ? 4 : 0
                    delegate: Rectangle {
                        z: 3
                        id: handle
                        property bool isLeftHandle: index % 2 === 0
                        property bool isTopHandle: index < 2
                        width: 12 * root.inv; height: 12 * root.inv
                        x: (isLeftHandle ? 0 : bx.width) - width / 2
                        y: (isTopHandle ? 0 : bx.height) - height / 2
                        radius: 3 * root.inv
                        color: Theme.surface
                        border.width: 2 * root.inv; border.color: Theme.accent
                        MouseArea {
                            anchors.centerIn: parent
                            width: 28 * root.inv; height: 28 * root.inv
                            cursorShape: (handle.isLeftHandle === handle.isTopHandle) ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor
                            property var orig
                            onPressed: { var g = boxModel.get(bx.bi); orig = { x0: g.x0, y0: g.y0, x1: g.x1, y1: g.y1 } }
                            onPositionChanged: (m) => {
                                if (!pressed) return
                                var p = mapToItem(stage, m.x, m.y)
                                var px = Math.max(0, Math.min(root.imgW, p.x)), py = Math.max(0, Math.min(root.imgH, p.y))
                                var o = orig
                                boxModel.set(bx.bi, {
                                    x0: handle.isLeftHandle ? Math.min(px, o.x1 - 3) : o.x0, x1: handle.isLeftHandle ? o.x1 : Math.max(px, o.x0 + 3),
                                    y0: handle.isTopHandle ? Math.min(py, o.y1 - 3) : o.y0, y1: handle.isTopHandle ? o.y1 : Math.max(py, o.y0 + 3) })
                            }
                            onReleased: root.boxCommitted(bx.bi, boxModel.get(bx.bi).x0, boxModel.get(bx.bi).y0, boxModel.get(bx.bi).x1, boxModel.get(bx.bi).y1)
                        }
                    }
                }
                // bouton supprimer
                Rectangle {
                    visible: bx.selected
                    width: 22 * root.inv; height: 22 * root.inv; radius: width / 2
                    x: bx.width - width / 2; y: -height - 4 * root.inv
                    color: Theme.danger
                    Icon { anchors.centerIn: parent; name: "x"; size: Math.max(4, 14 * root.inv); color: "#ffffff" }
                    MouseArea { anchors.fill: parent; anchors.margins: -6 * root.inv; cursorShape: Qt.PointingHandCursor
                                onClicked: { root.boxRemoved(bx.bi); root.selectedBox = -1 } }
                }
            }
        }

        // zone en cours de tracé
        Rectangle {
            id: draft
            visible: false
            color: "#3310b981"
            border.width: 2 * root.inv; border.color: Theme.accent
        }

        // poignée du curseur avant/après
        Rectangle {
            visible: root.showResult && root.compare
            x: root.split * root.imgW - width / 2
            y: root.imgH / 2 - height / 2
            width: 36 * root.inv; height: width; radius: width / 2
            color: Theme.accent
            Icon { anchors.centerIn: parent; name: "compare"; size: Math.max(6, 20 * root.inv); color: Theme.accentText }
            MouseArea {
                anchors.fill: parent; anchors.margins: -8 * root.inv
                cursorShape: Qt.SizeHorCursor
                onPositionChanged: (m) => {
                    if (!pressed) return
                    var p = mapToItem(stage, m.x, m.y)
                    root.split = Math.max(0.02, Math.min(0.98, p.x / root.imgW))
                }
            }
        }
    }

    // =============================================================== barre d'outils flottante
    Rectangle {
        anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: Theme.space3
        height: 44; width: tools.implicitWidth + 16; radius: Theme.radiusM
        color: Theme.surfaceTop; border.width: 1; border.color: Theme.borderStrong
        visible: root.imgW > 0
        Row {
            id: tools
            anchors.centerIn: parent
            spacing: 2
            IconButton { iconName: "hand"; tip: appBackend.tr("Déplacer (ou maintenir Espace)", appBackend.language); active: root.panTool; size: 32; onClicked: root.panTool = !root.panTool }
            IconButton { iconName: "zoom-out"; tip: appBackend.tr("Zoom arrière (-)", appBackend.language); size: 32; onClicked: root.zoomAt(root.width / 2, root.height / 2, 1 / 1.25) }
            AppText { text: Math.round(root.zoom * 100) + " %"; role: "small"; width: 48; horizontalAlignment: Text.AlignHCenter; anchors.verticalCenter: parent.verticalCenter }
            IconButton { iconName: "zoom-in"; tip: appBackend.tr("Zoom avant (+)", appBackend.language); size: 32; onClicked: root.zoomAt(root.width / 2, root.height / 2, 1.25) }
            IconButton { iconName: "fit"; tip: appBackend.tr("Ajuster à la fenêtre (0)", appBackend.language); size: 32; onClicked: root.fit() }
        }
    }
}
