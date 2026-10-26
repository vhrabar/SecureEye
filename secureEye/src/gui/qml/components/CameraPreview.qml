pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

// Live view of a daemon-side camera session: the preview, the detected faces and what the daemon sees right now.
Item {
    id: preview

    required property CameraSession session
    property bool mirrored: true

    // A sentence for the latest frame, or for the session while it has none yet.
    readonly property string statusText: {
        if (preview.session.state === CameraSession.State.Waiting) {
            return qsTr("Waiting for the camera…");
        }
        switch (preview.session.frameState) {
        case "black":
            return qsTr("The camera image is black");
        case "dark":
            return qsTr("Too dark to see a face");
        case "no_face":
            return qsTr("Looking for your face…");
        case "multiple":
            return qsTr("More than one face in view");
        case "face":
            return preview.session.mode === CameraSession.Mode.Enroll ? qsTr("Face found, hold still") : qsTr("Face found, but not recognized");
        case "match":
            return qsTr("Recognized");
        default:
            return "";
        }
    }

    readonly property color faceColor: {
        switch (preview.session.frameState) {
        case "match":
            return Kirigami.Theme.positiveTextColor;
        case "multiple":
            return Kirigami.Theme.negativeTextColor;
        default:
            return Kirigami.Theme.highlightColor;
        }
    }

    implicitHeight: Kirigami.Units.gridUnit * 15
    implicitWidth: Kirigami.Units.gridUnit * 20

    Rectangle {
        anchors.fill: parent
        color: "black"
        radius: Kirigami.Units.cornerRadius
    }

    PreviewImage {
        id: image

        anchors.fill: parent
        mirrored: preview.mirrored
        session: preview.session
    }

    // Same geometry as the drawn image, so face boxes (fractions of it) line up at any size.
    Item {
        x: image.paintedRect.x
        y: image.paintedRect.y
        width: image.paintedRect.width
        height: image.paintedRect.height

        Repeater {
            model: preview.session.faces

            Rectangle {
                required property rect modelData

                border.color: preview.faceColor
                border.width: 2
                color: "transparent"
                radius: Kirigami.Units.cornerRadius
                x: (preview.mirrored ? 1 - modelData.x - modelData.width : modelData.x) * parent.width
                y: modelData.y * parent.height
                width: modelData.width * parent.width
                height: modelData.height * parent.height
            }
        }
    }

    Kirigami.PlaceholderMessage {
        anchors.centerIn: parent
        icon.name: "camera-web"
        text: {
            if (preview.session.active) {
                return qsTr("Starting the camera…");
            }
            // before a session the camera is simply not on yet; it is never opened without Start
            return preview.session.state === CameraSession.State.Idle ? qsTr("The camera turns on when you press Start") : qsTr("Camera off");
        }
        visible: !preview.session.hasPreview
        width: parent.width - Kirigami.Units.gridUnit * 4

        Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
        Kirigami.Theme.inherit: false
    }

    // Always visible while the daemon holds the camera, so it is obvious when it is on.
    Rectangle {
        anchors.left: parent.left
        anchors.margins: Kirigami.Units.smallSpacing
        anchors.top: parent.top
        color: Qt.rgba(0, 0, 0, 0.6)
        implicitHeight: cameraOn.implicitHeight + Kirigami.Units.smallSpacing * 2
        implicitWidth: cameraOn.implicitWidth + Kirigami.Units.largeSpacing * 2
        radius: height / 2
        visible: preview.session.state === CameraSession.State.Running

        RowLayout {
            id: cameraOn

            anchors.centerIn: parent
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                color: Kirigami.Theme.negativeTextColor
                implicitHeight: implicitWidth
                implicitWidth: Kirigami.Units.gridUnit * 0.5
                radius: width / 2
            }
            Controls.Label {
                color: "white"
                text: qsTr("Camera on")
            }
        }
    }

    Rectangle {
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.margins: Kirigami.Units.largeSpacing
        color: Qt.rgba(0, 0, 0, 0.6)
        implicitHeight: status.implicitHeight + Kirigami.Units.smallSpacing * 2
        implicitWidth: status.implicitWidth + Kirigami.Units.largeSpacing * 2
        radius: Kirigami.Units.cornerRadius
        visible: preview.statusText.length > 0 && preview.session.active

        Controls.Label {
            id: status

            anchors.centerIn: parent
            color: "white"
            text: preview.statusText
        }
    }
}
