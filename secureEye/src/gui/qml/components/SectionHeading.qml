import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Title and short description at the top of a page or section.
ColumnLayout {
    id: heading

    property string title
    property string description
    property int level: 1

    spacing: Kirigami.Units.smallSpacing

    Kirigami.Heading {
        Layout.fillWidth: true
        level: heading.level
        text: heading.title
        wrapMode: Text.WordWrap
    }
    Controls.Label {
        Layout.fillWidth: true
        opacity: 0.7
        text: heading.description
        visible: heading.description.length > 0
        wrapMode: Text.WordWrap
    }
}
