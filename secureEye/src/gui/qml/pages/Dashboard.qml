import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

Kirigami.ScrollablePage {
    title: "Dashboard"

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeading {
            Layout.fillWidth: true
            description: "Status overview for face authentication on this machine."
            title: "Dashboard"
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
                            checked: true
                        }
                    }
                    Kirigami.Heading {
                        color: Kirigami.Theme.positiveTextColor
                        level: 1
                        text: "Enabled"
                    }
                    Controls.Label {
                        Layout.fillWidth: true
                        opacity: 0.5
                        text: "PAM module active for this account (core.disabled = false)"
                        wrapMode: Text.WordWrap
                    }
                }
            }
            // Placeholder values until the daemon and camera status come over the socket (#24).
            StatusCard {
                caption: "DAEMON"
                detail: "secureeye-authd.service"
                state: StatusCard.State.Ok
                status: "Active"
            }
            StatusCard {
                caption: "CAMERA"
                detail: "/dev/video0"
                state: StatusCard.State.Ok
                status: "Connected"
            }
        }

        // Action buttons 
        RowLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Button {
                highlighted: true
                text: "Run recognition test"
            }
            Controls.Button {
                text: "Enroll a face model"
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
                    opacity: 0.6
                    text: "Daemon service, IPC socket, PAM enrollment detail"
                }
            }
        }

        // push everything to the top
        Item {
            Layout.fillHeight: true
        }
    }
}
