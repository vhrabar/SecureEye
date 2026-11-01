import QtQuick
import QtQuick.Controls as Controls

// On/off editor. The value comes in as a property and changes go out through edited().
Controls.Switch {
    id: toggle

    property bool value

    signal edited(bool value)

    checked: toggle.value

    onToggled: toggle.edited(toggle.checked)
}
