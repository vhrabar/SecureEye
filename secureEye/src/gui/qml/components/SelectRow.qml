import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Picks one of a fixed set of values, shown with their labels.
Controls.ComboBox {
    id: select

    property string value
    property var values: []
    property var labels: []

    signal edited(string value)

    currentIndex: select.values.indexOf(select.value)
    implicitWidth: Kirigami.Units.gridUnit * 20
    model: select.labels.length > 0 ? select.labels : select.values

    onActivated: index => select.edited(select.values[index])
}
