pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

// Match the camera against the user's face models for a while, through secureeye-authd, and show how close each
// frame comes to the certainty threshold. Nothing is logged in and nothing is saved.
Kirigami.Dialog {
    id: dialog

    readonly property int durationMs: 15000

    // Counted here from the frame reports; the daemon's own totals arrive with the result.
    property int frames: 0
    property int matchedFrames: 0

    readonly property bool hasDistance: !isNaN(session.distance)
    readonly property bool hasCertainty: !isNaN(session.certainty)
    // The meter runs from 0 to twice the threshold, so the threshold sits in the middle.
    readonly property real meterMax: dialog.hasCertainty ? session.certainty * 2 : 7

    readonly property var summary: {
        if (session.state !== CameraSession.State.Finished) {
            return null;
        }
        if (session.result !== "completed") {
            return {
                type: session.result === "cancelled" ? Kirigami.MessageType.Information : Kirigami.MessageType.Error,
                text: session.resultMessage
            };
        }
        const data = session.resultData;
        const best = data.best_distance;
        const certainty = dialog.hasCertainty ? session.certainty.toFixed(1) : "?";
        if (data.matched_frames > 0) {
            return {
                type: Kirigami.MessageType.Positive,
                text: "Recognized in %1 of %2 frames. Closest distance %3; certainty is %4.".arg(data.matched_frames).arg(data.frames).arg(best.toFixed(2)).arg(certainty)
            };
        }
        if (best === null || best === undefined) {
            return {
                type: Kirigami.MessageType.Warning,
                text: "No face was compared with your models. Look into the camera during the test, in enough light."
            };
        }
        return {
            type: Kirigami.MessageType.Warning,
            text: "Not recognized. The closest distance was %1, but certainty is %2. Enroll another face model in this light, or raise certainty in the configuration (less secure).".arg(best.toFixed(2)).arg(certainty)
        };
    }

    padding: Kirigami.Units.largeSpacing
    preferredWidth: Kirigami.Units.gridUnit * 32
    standardButtons: Kirigami.Dialog.NoButton
    title: "Recognition test"

    customFooterActions: [
        Kirigami.Action {
            icon.name: "media-playback-start"
            text: session.state === CameraSession.State.Finished ? "Run again" : "Start"
            visible: !session.active

            onTriggered: {
                dialog.frames = 0;
                dialog.matchedFrames = 0;
                session.start();
            }
        },
        Kirigami.Action {
            icon.name: "media-playback-stop"
            text: "Stop"
            visible: session.active

            onTriggered: session.cancel()
        },
        Kirigami.Action {
            icon.name: "dialog-close"
            text: "Close"
            visible: !session.active

            onTriggered: dialog.close()
        }
    ]

    // before the dialog shows, so the last run's picture and result never flash up while it opens
    onAboutToShow: {
        dialog.frames = 0;
        dialog.matchedFrames = 0;
        session.reset();
    }
    onClosed: session.reset()

    CameraSession {
        id: session

        durationMs: dialog.durationMs
        mode: CameraSession.Mode.Test

        onFrameChanged: {
            // frameChanged also fires when a session is reset, with no frame state
            if (session.frameState === "") {
                return;
            }
            dialog.frames += 1;
            if (session.frameState === "match") {
                dialog.matchedFrames += 1;
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        CameraPreview {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 18
            session: session
        }
        Controls.Label {
            Layout.fillWidth: true
            opacity: 0.7
            text: "Look into the camera as you would when logging in. For %1 seconds every frame is compared with your face models; nothing is saved.".arg(dialog.durationMs / 1000)
            visible: session.state === CameraSession.State.Idle
            wrapMode: Text.WordWrap
        }

        // Distance meter: lower is a closer match; the marker is the certainty threshold.
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            visible: session.state === CameraSession.State.Running || dialog.frames > 0

            RowLayout {
                Layout.fillWidth: true

                Controls.Label {
                    Layout.fillWidth: true
                    text: dialog.hasDistance ? "Distance %1".arg(session.distance.toFixed(2)) : "Distance –"
                }
                Controls.Label {
                    opacity: 0.7
                    text: dialog.hasCertainty ? "match at %1 or less".arg(session.certainty.toFixed(1)) : ""
                }
            }
            Item {
                Layout.fillWidth: true
                implicitHeight: Kirigami.Units.gridUnit * 0.75

                Rectangle {
                    anchors.fill: parent
                    color: Kirigami.Theme.alternateBackgroundColor
                    radius: height / 2
                }
                Rectangle {
                    color: session.frameState === "match" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor
                    height: parent.height
                    radius: height / 2
                    visible: dialog.hasDistance
                    width: Math.max(height, Math.min(1, session.distance / dialog.meterMax) * parent.width)

                    Behavior on width {
                        NumberAnimation {
                            duration: Kirigami.Units.shortDuration
                        }
                    }
                }
                // the threshold
                Rectangle {
                    color: Kirigami.Theme.textColor
                    height: parent.height + Kirigami.Units.smallSpacing * 2
                    visible: dialog.hasCertainty
                    width: 2
                    x: parent.width / 2 - width / 2
                    y: -Kirigami.Units.smallSpacing
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                opacity: 0.7
                text: "Recognized in %1 of %2 frames".arg(dialog.matchedFrames).arg(dialog.frames)
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            text: dialog.summary !== null ? dialog.summary.text : ""
            type: dialog.summary !== null ? dialog.summary.type : Kirigami.MessageType.Information
            visible: dialog.summary !== null
        }
    }
}
