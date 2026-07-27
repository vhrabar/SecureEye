import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page

    padding: 0
    title: "Configuration"

    footer: Kirigami.NavigationTabBar {
        actions: [
            Kirigami.Action {
                checked: swipeView.currentIndex === 0
                icon.name: "settings-configure"
                text: "Core"

                onTriggered: swipeView.currentIndex = 0
            },
            Kirigami.Action {
                checked: swipeView.currentIndex === 1
                icon.name: "camera-web"
                text: "Video"

                onTriggered: swipeView.currentIndex = 1
            },
            Kirigami.Action {
                checked: swipeView.currentIndex === 2
                icon.name: "image-x-generic"
                text: "Snapshots"

                onTriggered: swipeView.currentIndex = 2
            },
            Kirigami.Action {
                checked: swipeView.currentIndex === 3
                icon.name: "tools-report-bug"
                text: "Debug"

                onTriggered: swipeView.currentIndex = 3
            }
        ]
    }

    Controls.SwipeView {
        id: swipeView

        anchors.fill: parent
        clip: true

        ConfigSection {
            description: "PAM behaviour, notices and the face detector backend."
            section: "core"
        }
        ConfigSection {
            description: "Capture device, timeout and recognition certainty."
            section: "video"
        }
        ConfigSection {
            description: "Saving snapshots of failed and successful attempts."
            section: "snapshots"
        }
        ConfigSection {
            description: "Diagnostic reports and verbose logging."
            section: "debug"
        }
    }

    component ConfigSection: Controls.ScrollView {
        id: sectionView

        required property string description
        required property string section

        Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            width: sectionView.availableWidth

            Kirigami.Heading {
                Layout.margins: Kirigami.Units.largeSpacing
                level: 1
                text: "[%1]".arg(sectionView.section)
            }
            Controls.Label {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                opacity: 0.7
                text: sectionView.description
                wrapMode: Text.WordWrap
            }
            Item {
                Layout.fillHeight: true
            }
        }
    }
}