pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

Kirigami.Page {
    id: page

    // Only the icons are page specific, everything else about a section comes
    // from ConfigSchema.hpp through ConfigModel.
    readonly property var sectionIcons: ({
            core: "settings-configure",
            video: "camera-web",
            snapshots: "image-x-generic",
            debug: "tools-report-bug"
        })

    padding: 0
    title: "Configuration"

    actions: [
        Kirigami.Action {
            enabled: ConfigStore.dirty
            icon.name: "document-revert"
            text: "Discard"

            onTriggered: ConfigStore.revert()
        },
        Kirigami.Action {
            enabled: ConfigStore.dirty
            icon.name: "document-save"
            text: "Save"

            onTriggered: ConfigStore.save()
        }
    ]
    footer: Kirigami.NavigationTabBar {
        // One tab per schema section. Rebuilt whenever the instantiator's count
        // changes, which for a compile time schema means once, at startup.
        actions: Array.from({
            length: tabs.count
        }, (unused, at) => tabs.objectAt(at))

        Instantiator {
            id: tabs

            model: ConfigModel.sections()

            delegate: Kirigami.Action {
                required property int index
                required property var modelData

                checked: swipeView.currentIndex === index
                icon.name: page.sectionIcons[modelData.name] ?? "settings-configure"
                text: modelData.title

                onTriggered: swipeView.currentIndex = index
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Kirigami.InlineMessage {
            id: statusMessage

            Layout.fillWidth: true
            position: Kirigami.InlineMessage.Position.Header
            showCloseButton: true
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            position: Kirigami.InlineMessage.Position.Header
            text: "%1 is read only for this user, so changes cannot be saved yet.".arg(ConfigStore.path)
            type: Kirigami.MessageType.Information
            visible: !ConfigStore.writable
        }
        Controls.SwipeView {
            id: swipeView

            Layout.fillHeight: true
            Layout.fillWidth: true
            clip: true

            Repeater {
                model: ConfigModel.sections()

                delegate: ConfigSectionView {
                    required property var modelData

                    section: modelData.name
                }
            }
        }
    }

    Connections {
        function onSaveFinished(ok: bool, error: string): void {
            statusMessage.text = ok ? "Configuration saved to %1.".arg(ConfigStore.path) : error;
            statusMessage.type = ok ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error;
            statusMessage.visible = true;
        }

        target: ConfigStore
    }

    component ConfigSectionView: Controls.ScrollView {
        id: sectionView

        required property string section

        readonly property var info: ConfigModel.sectionInfo(sectionView.section)

        Controls.ScrollBar.horizontal.policy: Controls.ScrollBar.AlwaysOff

        ColumnLayout {
            spacing: Kirigami.Units.largeSpacing
            width: sectionView.availableWidth

            Kirigami.Heading {
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.topMargin: Kirigami.Units.largeSpacing
                level: 1
                text: sectionView.info.title
            }
            Controls.Label {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                opacity: 0.7
                text: sectionView.info.description
                wrapMode: Text.WordWrap
            }
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Repeater {
                    model: ConfigSectionFilter {
                        section: sectionView.section
                        sourceModel: ConfigModel
                    }

                    delegate: ConfigRow {
                    }
                }
            }
            Item {
                Layout.fillHeight: true
            }
        }
    }
}
