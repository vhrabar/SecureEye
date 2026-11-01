import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Free text editor. Reports the text once editing is finished, not on every keystroke.
Loader {
    id: textRow

    property string value
    property bool multiline: false

    signal edited(string value)

    sourceComponent: textRow.multiline ? areaEditor : fieldEditor

    Component {
        id: fieldEditor

        Controls.TextField {
            implicitWidth: Kirigami.Units.gridUnit * 20
            text: textRow.value

            onEditingFinished: textRow.edited(text)
        }
    }
    Component {
        id: areaEditor

        Controls.TextArea {
            implicitWidth: Kirigami.Units.gridUnit * 20
            text: textRow.value
            wrapMode: TextEdit.Wrap

            onEditingFinished: textRow.edited(text)
        }
    }
}
