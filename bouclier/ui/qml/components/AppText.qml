import QtQuick

Text {
    property string role: "body"   // body | muted | small | title | hero | lead
    color: role === "muted" || role === "small" ? Theme.textMuted : Theme.text
    font.family: Theme.fontFamily
    font.pixelSize: role === "hero" ? Theme.fsHero : role === "title" ? Theme.fsTitle
                  : role === "lead" ? Theme.fsLead : role === "small" ? Theme.fsSmall : Theme.fsBody
    font.weight: role === "hero" || role === "title" ? Font.DemiBold : role === "lead" ? Font.Medium : Font.Normal
    wrapMode: Text.Wrap
    elide: Text.ElideNone
    textFormat: Text.PlainText
    Behavior on color { ColorAnimation { duration: Theme.durMed } }
}
