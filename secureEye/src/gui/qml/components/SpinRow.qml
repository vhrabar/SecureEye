import QtQuick
import QtQuick.Controls as Controls

// Whole number editor. Uses SpinBox's own value property as its input.
Controls.SpinBox {
    id: spin

    signal edited(int value)

    editable: true

    onValueModified: spin.edited(spin.value)
}
