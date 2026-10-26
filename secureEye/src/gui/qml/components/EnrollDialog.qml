pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

// Capture a new face model through secureeye-authd, with a live preview. Self-contained, so any page can open it.
// Closing the dialog in any way drops the session, which gives the camera back right away.
Kirigami.Dialog {
    id: dialog

    // Emitted after a model was saved, so a page showing the models can reload them.
    signal enrolled

    // Same default as `secureEye add`.
    readonly property string suggestedLabel: "Model #%1".arg(models.nextModelId)
    readonly property string label: labelField.text.trim().length > 0 ? labelField.text.trim() : dialog.suggestedLabel
    readonly property bool succeeded: session.state === CameraSession.State.Finished && session.result === "success"

    padding: Kirigami.Units.largeSpacing
    preferredWidth: Kirigami.Units.gridUnit * 32
    standardButtons: Kirigami.Dialog.NoButton
    title: replaceBox.checked ? "Re-enroll your face" : "Enroll a face model"

    customFooterActions: [
        Kirigami.Action {
            enabled: dialog.label.length <= 64
            icon.name: "camera-photo"
            text: session.state === CameraSession.State.Finished ? "Try again" : "Start"
            visible: !session.active && !dialog.succeeded

            onTriggered: session.start()
        },
        Kirigami.Action {
            icon.name: "dialog-cancel"
            text: "Stop"
            visible: session.active

            onTriggered: session.cancel()
        },
        Kirigami.Action {
            icon.name: dialog.succeeded ? "dialog-ok" : "dialog-close"
            text: dialog.succeeded ? "Done" : "Close"
            visible: !session.active

            onTriggered: dialog.close()
        }
    ]

    onOpened: {
        session.reset();
        labelField.text = "";
        replaceBox.checked = false;
        models.refresh();
    }
    onClosed: session.reset()

    ModelStore {
        id: models
    }
    CameraSession {
        id: session

        label: dialog.label
        mode: CameraSession.Mode.Enroll
        replace: replaceBox.checked

        onFinished: result => {
            if (result === "success") {
                dialog.enrolled();
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
            text: "Look straight into the camera in even light, with only you in view. The model is taken from the first frame that shows exactly one face."
            visible: session.state === CameraSession.State.Idle
            wrapMode: Text.WordWrap
        }
        Kirigami.FormLayout {
            Layout.fillWidth: true
            enabled: !session.active && !dialog.succeeded

            Controls.TextField {
                id: labelField

                Kirigami.FormData.label: "Label:"
                maximumLength: 64
                placeholderText: dialog.suggestedLabel
            }
            Controls.CheckBox {
                id: replaceBox

                Kirigami.FormData.label: "Existing models:"
                text: "Replace them (re-enroll)"
                visible: models.count > 0
            }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            text: session.resultMessage
            type: dialog.succeeded ? Kirigami.MessageType.Positive : session.result === "cancelled" ? Kirigami.MessageType.Information : Kirigami.MessageType.Error
            visible: session.state === CameraSession.State.Finished
        }
    }
}
