import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

Kirigami.ScrollablePage {
    id: page

    property string devicePath: ConfigStore.value("video", "device_path")

    // systemd's ActiveState of the daemon, mapped onto a status card.
    readonly property var daemonStatus: {
        if (!DaemonController.installed) {
            return {
                state: StatusCard.State.Error,
                text: "Not installed"
            };
        }
        switch (DaemonController.activeState) {
        case "active":
            return {
                state: StatusCard.State.Ok,
                text: "Running"
            };
        case "activating":
        case "reloading":
            return {
                state: StatusCard.State.Warning,
                text: "Starting"
            };
        case "deactivating":
            return {
                state: StatusCard.State.Warning,
                text: "Stopping"
            };
        case "failed":
            return {
                state: StatusCard.State.Error,
                text: "Failed"
            };
        case "inactive":
            return {
                state: StatusCard.State.Error,
                text: "Stopped"
            };
        default:
            return {
                state: StatusCard.State.Unknown,
                text: "Unknown"
            };
        }
    }

    function showError(message: string): void {
        errorMessage.text = message;
        errorMessage.visible = true;
    }

    title: "Dashboard"

    CameraDevice {
        id: camera

        path: page.devicePath
    }
    EnrollDialog {
        id: enrollDialog
    }
    RecognitionTestDialog {
        id: testDialog
    }
    Connections {
        function onFailed(message: string): void {
            page.showError(message);
        }

        target: DaemonController
    }
    Connections {
        function onValueChanged(section: string, key: string): void {
            if (section === "video" && key === "device_path") {
                page.devicePath = ConfigStore.value("video", "device_path");
            }
        }

        target: ConfigStore
    }
    Connections {
        function onFailed(message: string): void {
            page.showError(message);
        }

        target: PamStatus
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeading {
            Layout.fillWidth: true
            description: "Status overview for face authentication on this machine."
            title: "Dashboard"
        }
        Kirigami.InlineMessage {
            id: errorMessage

            Layout.fillWidth: true
            showCloseButton: true
            type: Kirigami.MessageType.Error
        }

        // Status cards 
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            Kirigami.AbstractCard {
                Layout.fillHeight: true
                Layout.fillWidth: true
                Layout.preferredWidth: Kirigami.Units.gridUnit * 12

                contentItem: ColumnLayout {
                    spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        Layout.fillWidth: true

                        Controls.Label {
                            Layout.fillWidth: true
                            font.bold: true
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            opacity: 0.6
                            text: "FACE AUTHENTICATION"
                        }
                        Controls.Switch {
                            id: pamSwitch

                            // Applies right away (with a polkit prompt) instead of waiting for Save on the
                            // Configuration page.
                            checked: PamStatus.enabled
                            enabled: !PamStatus.busy

                            onToggled: {
                                PamStatus.setEnabled(pamSwitch.checked);
                                // Clicking breaks the binding; restore it so the switch follows the real state, and
                                // flips back when the change is refused or cancelled.
                                pamSwitch.checked = Qt.binding(() => PamStatus.enabled);
                            }
                        }
                    }
                    Kirigami.Heading {
                        color: PamStatus.enabled ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor
                        level: 1
                        text: PamStatus.busy ? "Switching…" : PamStatus.enabled ? "Enabled" : "Disabled"
                    }
                    Controls.Label {
                        Layout.fillWidth: true
                        opacity: 0.5
                        text: "core.disabled = %1".arg(PamStatus.enabled ? "false" : "true")
                        wrapMode: Text.WordWrap
                    }
                }
            }
            StatusCard {
                caption: "DAEMON"
                detail: DaemonController.subState
                    ? "%1 (%2)".arg(DaemonController.unitName).arg(DaemonController.subState)
                    : DaemonController.unitName
                state: page.daemonStatus.state
                status: page.daemonStatus.text
            }
            // The configured device node; whether the daemon can open it shows once a session runs.
            StatusCard {
                caption: "CAMERA"
                detail: {
                    switch (camera.status) {
                    case CameraDevice.Status.NotSet:
                        return "Set video.device_path in the configuration";
                    case CameraDevice.Status.Present:
                        return camera.name ? "%1 (%2)".arg(camera.name).arg(camera.path) : camera.path;
                    default:
                        return camera.path;
                    }
                }
                state: {
                    switch (camera.status) {
                    case CameraDevice.Status.Present:
                        return StatusCard.State.Ok;
                    case CameraDevice.Status.NotSet:
                        return StatusCard.State.Warning;
                    default:
                        return StatusCard.State.Error;
                    }
                }
                status: {
                    switch (camera.status) {
                    case CameraDevice.Status.Present:
                        return "Found";
                    case CameraDevice.Status.NotSet:
                        return "Not set";
                    default:
                        return "Not found";
                    }
                }
            }
        }

        // Action buttons 
        RowLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Button {
                highlighted: true
                text: "Run recognition test"

                onClicked: testDialog.open()
            }
            Controls.Button {
                text: "Enroll a face model"

                onClicked: enrollDialog.open()
            }
        }

        // Advanced section 
        Kirigami.AbstractCard {
            Layout.fillWidth: true

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Heading {
                    level: 3
                    text: "Advanced & system control"
                }
                Controls.Label {
                    Layout.fillWidth: true
                    opacity: 0.6
                    text: "Start, stop or restart the authentication daemon. Face login does not work while it is stopped."
                    wrapMode: Text.WordWrap
                }
                RowLayout {
                    enabled: DaemonController.installed && !DaemonController.busy
                    spacing: Kirigami.Units.smallSpacing

                    Controls.Button {
                        enabled: DaemonController.activeState !== "active"
                        icon.name: "media-playback-start"
                        text: "Start"

                        onClicked: DaemonController.start()
                    }
                    Controls.Button {
                        enabled: DaemonController.activeState === "active"
                        icon.name: "media-playback-stop"
                        text: "Stop"

                        onClicked: DaemonController.stop()
                    }
                    Controls.Button {
                        enabled: DaemonController.activeState === "active"
                        icon.name: "view-refresh"
                        text: "Restart"

                        onClicked: DaemonController.restart()
                    }
                    Controls.BusyIndicator {
                        Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                        Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                        running: DaemonController.busy
                        visible: running
                    }
                }
            }
        }

        // push everything to the top
        Item {
            Layout.fillHeight: true
        }
    }
}
