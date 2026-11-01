import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Status tile: caption, coloured state dot with a short status, and a detail line.
Kirigami.AbstractCard {
    id: card

    enum State {
        Unknown,
        Ok,
        Warning,
        Error
    }

    property string caption
    property string status
    property string detail
    property int state: StatusCard.State.Unknown

    readonly property color stateColor: {
        switch (card.state) {
        case StatusCard.State.Ok:
            return Kirigami.Theme.positiveTextColor;
        case StatusCard.State.Warning:
            return Kirigami.Theme.neutralTextColor;
        case StatusCard.State.Error:
            return Kirigami.Theme.negativeTextColor;
        default:
            return Kirigami.Theme.disabledTextColor;
        }
    }

    Layout.fillHeight: true
    Layout.fillWidth: true
    Layout.preferredWidth: Kirigami.Units.gridUnit * 12

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        Controls.Label {
            Layout.fillWidth: true
            elide: Text.ElideRight
            font.bold: true
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            opacity: 0.6
            text: card.caption
        }
        RowLayout {
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                color: card.stateColor
                implicitHeight: implicitWidth
                implicitWidth: Kirigami.Units.gridUnit * 0.5
                radius: width / 2
            }
            Kirigami.Heading {
                Layout.fillWidth: true
                elide: Text.ElideRight
                level: 1
                text: card.status
            }
        }
        Controls.Label {
            Layout.fillWidth: true
            font.family: "monospace"
            opacity: 0.5
            text: card.detail
            visible: card.detail.length > 0
            wrapMode: Text.WrapAnywhere
        }
    }
}
