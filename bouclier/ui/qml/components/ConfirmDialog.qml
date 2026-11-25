import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Popup {
    id: root
    property string title: ""
    property string message: ""
    property string confirmText: appBackend.tr("Confirmer", appBackend.language)
    property bool destructive: true
    signal confirmed()
    modal: true
    focus: true
    anchors.centerIn: Overlay.overlay
    width: 420
    padding: Theme.space5
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    enter: Transition { ParallelAnimation {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.durMed }
        NumberAnimation { property: "scale"; from: 0.95; to: 1; duration: Theme.durMed; easing.type: Theme.easing } } }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.durFast } }
    Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { radius: Theme.radiusL; color: Theme.surface; border.width: 1; border.color: Theme.borderStrong }
    contentItem: ColumnLayout {
        spacing: Theme.space3
        AppText { text: root.title; role: "lead"; Layout.fillWidth: true }
        AppText { text: root.message; role: "muted"; Layout.fillWidth: true }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Layout.topMargin: Theme.space3
            spacing: Theme.space2
            AppButton { text: appBackend.tr("Annuler", appBackend.language); variant: "ghost"; onClicked: root.close() }
            AppButton { text: root.confirmText; variant: root.destructive ? "danger" : "primary"; onClicked: { root.close(); root.confirmed() } }
        }
    }
}
