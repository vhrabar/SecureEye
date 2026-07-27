import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    title: "Dashboard"

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        // Header 
        Kirigami.Heading {
            level: 1
            text: "Dashboard"
        }
        Controls.Label {
            Layout.fillWidth: true
            opacity: 0.7
            text: "Status overview for face authentication on this machine."
            wrapMode: Text.WordWrap
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
            DotStatusCard {
                caption: "DAEMON"
                detail: "secureeye-authd.service"
                status: "Active"
            }
            DotStatusCard {
                caption: "CAMERA"
                detail: "/dev/video0"
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

    // A status card with a coloured status dot (Daemon / Camera)
    component DotStatusCard: Kirigami.AbstractCard {
        property string caption
        property string detail
        property string status

        Layout.fillHeight: true
        Layout.fillWidth: true
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Controls.Label {
                font.bold: true
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                opacity: 0.6
                text: caption
            }
            RowLayout {
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    color: Kirigami.Theme.positiveTextColor
                    implicitHeight: implicitWidth
                    implicitWidth: Kirigami.Units.gridUnit * 0.5
                    radius: width / 2
                }
                Kirigami.Heading {
                    level: 1
                    text: status
                }
            }
            Controls.Label {
                Layout.fillWidth: true
                font.family: "monospace"
                opacity: 0.5
                text: detail
                wrapMode: Text.WordWrap
            }
        }
    }
}