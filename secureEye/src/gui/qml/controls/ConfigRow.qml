pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

// One option of config.ini as a form row: the editor for its type, an unsaved marker, reset and help.
// It only reports changes; the page decides what to do with them.
RowLayout {
    id: row

    required property bool applicable
    required property string defaultValue
    required property var enumLabels
    required property var enumValues
    required property bool hasRange
    required property string help
    required property string key
    required property string label
    required property real maximum
    required property real minimum
    required property bool modified
    required property string note
    required property string section
    required property var value
    required property int valueType

    signal edited(var value)
    signal resetRequested

    Kirigami.FormData.label: "%1:".arg(row.label)
    enabled: row.applicable
    spacing: Kirigami.Units.smallSpacing

    Loader {
        id: editor

        sourceComponent: {
            switch (row.valueType) {
            case ConfigOptionType.Bool:
                return boolEditor;
            case ConfigOptionType.Int:
                return intEditor;
            case ConfigOptionType.Float:
                return floatEditor;
            case ConfigOptionType.Enum:
                return enumEditor;
            case ConfigOptionType.Multiline:
                return multilineEditor;
            default:
                return textEditor;
            }
        }
    }
    // Marks a row the user has changed but not saved yet.
    Kirigami.Icon {
        Layout.preferredHeight: Kirigami.Units.iconSizes.small
        Layout.preferredWidth: Kirigami.Units.iconSizes.small
        color: Kirigami.Theme.neutralTextColor
        opacity: row.modified ? 1 : 0
        source: "emblem-important-symbolic"

        Controls.ToolTip.text: "Unsaved change"
        Controls.ToolTip.visible: modifiedHover.hovered

        HoverHandler {
            id: modifiedHover

        }
    }
    Controls.ToolButton {
        display: Controls.AbstractButton.IconOnly
        enabled: String(row.value) !== row.defaultValue
        icon.name: "edit-undo-symbolic"
        text: "Reset to default (%1)".arg(row.defaultValue)

        Controls.ToolTip.text: text
        Controls.ToolTip.visible: hovered

        onClicked: row.resetRequested()
    }
    Kirigami.ContextualHelpButton {
        toolTipText: row.note ? "%1\n\n(%2)".arg(row.help).arg(row.note) : row.help
    }

    Component {
        id: boolEditor

        ToggleRow {
            value: row.value === true

            onEdited: value => row.edited(value)
        }
    }
    Component {
        id: intEditor

        SpinRow {
            from: row.hasRange ? Math.round(row.minimum) : -2147483647
            to: row.hasRange ? Math.round(row.maximum) : 2147483647
            value: row.value

            onEdited: value => row.edited(value)
        }
    }
    Component {
        id: floatEditor

        SliderRow {
            from: row.hasRange ? row.minimum : 0
            to: row.hasRange ? row.maximum : 100
            value: row.value

            onEdited: value => row.edited(value)
        }
    }
    Component {
        id: enumEditor

        SelectRow {
            labels: row.enumLabels
            value: row.value
            values: row.enumValues

            onEdited: value => row.edited(value)
        }
    }
    Component {
        id: textEditor

        TextRow {
            value: row.value

            onEdited: value => row.edited(value)
        }
    }
    Component {
        id: multilineEditor

        TextRow {
            multiline: true
            value: row.value

            onEdited: value => row.edited(value)
        }
    }
}
