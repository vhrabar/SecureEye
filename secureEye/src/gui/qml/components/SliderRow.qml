import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Slider with a value readout, for numbers with a known range.
RowLayout {
    id: sliderRow

    property real value
    property real from: 0
    property real to: 100
    property real stepSize: 0.1
    readonly property int decimals: Math.max(0, Math.ceil(-Math.log10(sliderRow.stepSize)))

    signal edited(real value)

    spacing: Kirigami.Units.smallSpacing

    Controls.Slider {
        id: slider

        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        sliderRow.from
        stepSize: sliderRow.stepSize
        to: sliderRow.to
        value: sliderRow.value

        onMoved: sliderRow.edited(Number(slider.value.toFixed(sliderRow.decimals)))
    }
    Controls.Label {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 2
        text: Number(slider.value).toFixed(sliderRow.decimals)
    }
}
