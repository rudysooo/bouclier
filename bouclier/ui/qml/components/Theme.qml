pragma Singleton
import QtQuick

// Thème unique : couleurs, rayons, espacements, typographie, durées. `dark` est piloté depuis Main.qml.
QtObject {
    property bool dark: true

    // surfaces
    readonly property color bg:         dark ? "#090d16" : "#f3f5fa"
    readonly property color surface:    dark ? "#0f1626" : "#ffffff"
    readonly property color surfaceHi:  dark ? "#18223a" : "#eaeff8"
    readonly property color surfaceTop: dark ? "#1f2b49" : "#dfe6f3"
    readonly property color border:     dark ? "#223050" : "#d5ddec"
    readonly property color borderStrong: dark ? "#33466f" : "#b9c5dc"
    // texte (contrastes ≥ 4.5:1 sur les surfaces ci-dessus)
    readonly property color text:       dark ? "#f1f5f9" : "#0b1220"
    readonly property color textMuted:  dark ? "#9aa8c1" : "#4a5870"
    readonly property color textFaint:  dark ? "#6f7f9c" : "#66748c"
    // accent
    readonly property color accent:      "#10b981"
    readonly property color accentHover: dark ? "#34d399" : "#0ea271"
    readonly property color accentPress: dark ? "#0ea271" : "#0b8a61"
    readonly property color accentFg:    dark ? "#34d399" : "#047857"   // accent utilisé comme couleur de texte
    readonly property color accentText:    "#04140d"                      // texte posé sur un fond accent
    readonly property color accentSoft:  dark ? "#0f2f2a" : "#d9f5ea"
    // états
    readonly property color danger:  dark ? "#f87171" : "#c62828"
    readonly property color dangerSoft: dark ? "#3a1620" : "#fde4e4"
    readonly property color warning: dark ? "#fbbf24" : "#a15c00"
    readonly property color warningSoft: dark ? "#33260d" : "#fdf0d2"
    readonly property color info:    dark ? "#38bdf8" : "#0369a1"
    readonly property color infoSoft: dark ? "#0d2a3a" : "#dbeefa"
    readonly property color scrim: dark ? "#b3050810" : "#800b1220"
    readonly property color shadow: dark ? "#66000000" : "#2a1b2a4a"

    // géométrie
    readonly property int radiusS: 8
    readonly property int radiusM: 12
    readonly property int radiusL: 14
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space5: 24
    readonly property int space6: 32
    readonly property int railWidth: 76
    readonly property int panelWidth: 340

    // typographie
    readonly property string fontFamily: Qt.application.font.family
    readonly property int fsSmall: 12
    readonly property int fsBody: 14
    readonly property int fsLead: 16
    readonly property int fsTitle: 22
    readonly property int fsHero: 30

    // animation
    readonly property int durFast: 150
    readonly property int durMed: 200
    readonly property int durSlow: 250
    readonly property int easing: Easing.OutCubic
}
