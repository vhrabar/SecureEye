pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui


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

    Kirigami.FormData.label: "%1:".arg(row.label)
    enabled: row.applicable
    spacing: Kirigami.Units.smallSpacing

    function commit(newValue: var): void {
        ConfigStore.set(row.section, row.key, newValue);
    }

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

        onClicked: ConfigStore.reset(row.section, row.key)
    }
    Kirigami.ContextualHelpButton {
        toolTipText: row.note ? "%1\n\n(%2)".arg(row.help).arg(row.note) : row.help
    }

    Component {
        id: boolEditor

        Controls.Switch {
            checked: row.value === true

            onToggled: row.commit(checked)
        }
    }
    Component {
        id: intEditor

        Controls.SpinBox {
            editable: true
            from: row.hasRange ? Math.round(row.minimum) : -2147483647
            to: row.hasRange ? Math.round(row.maximum) : 2147483647
            value: row.value

            onValueModified: row.commit(value)
        }
    }
    Component {
        id: floatEditor

        RowLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Slider {
                id: slider

                Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                from: row.hasRange ? row.minimum : 0
                stepSize: 0.1
                to: row.hasRange ? row.maximum : 100
                value: row.value

                onMoved: row.commit(Number(value.toFixed(1)))
            }
            Controls.Label {
                Layout.minimumWidth: Kirigami.Units.gridUnit * 2
                text: Number(slider.value).toFixed(1)
            }
        }
    }
    Component {
        id: enumEditor

        Controls.ComboBox {
            implicitWidth: Kirigami.Units.gridUnit * 20
            currentIndex: row.enumValues.indexOf(row.value)
            model: row.enumLabels

            onActivated: index => row.commit(row.enumValues[index])
        }
    }
    Component {
        id: textEditor

        Controls.TextField {
            implicitWidth: Kirigami.Units.gridUnit * 20
            text: row.value

            onEditingFinished: row.commit(text)
        }
    }
    Component {
        id: multilineEditor

        Controls.TextArea {
            implicitWidth: Kirigami.Units.gridUnit * 20
            text: row.value
            wrapMode: TextEdit.Wrap

            onEditingFinished: row.commit(text)
        }
    }
}
