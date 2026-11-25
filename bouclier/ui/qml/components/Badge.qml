import QtQuick

Rectangle {
    property alias text: lbl.text
    property string tone: "neutral"  // neutral | success | warning | danger | info
    implicitHeight: 22
    implicitWidth: lbl.implicitWidth + 16
    radius: height / 2
    color: tone === "success" ? Theme.accentSoft : tone === "warning" ? Theme.warningSoft
         : tone === "danger" ? Theme.dangerSoft : tone === "info" ? Theme.infoSoft : Theme.surfaceHi
    AppText {
        id: lbl
        anchors.centerIn: parent
        role: "small"
        font.weight: Font.Medium
        color: parent.tone === "success" ? Theme.accentFg : parent.tone === "warning" ? Theme.warning
             : parent.tone === "danger" ? Theme.danger : parent.tone === "info" ? Theme.info : Theme.textMuted
    }
}
