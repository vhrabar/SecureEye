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
            enabled: ConfigStore.dirty && !ConfigStore.saving
            icon.name: "document-revert"
            text: "Discard"

            onTriggered: ConfigStore.revert()
        },
        Kirigami.Action {
            enabled: ConfigStore.dirty && ConfigStore.canSave && !ConfigStore.saving
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
            text: ConfigStore.canSave
                ? "Saving %1 asks for administrator privileges.".arg(ConfigStore.path)
                : "%1 is read only for this user and is not the installed configuration, so changes cannot be saved.".arg(ConfigStore.path)
            type: ConfigStore.canSave ? Kirigami.MessageType.Information : Kirigami.MessageType.Warning
            visible: !ConfigStore.writable
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            position: Kirigami.InlineMessage.Position.Header
            text: "%1 was changed outside SecureEye Manager while you had unsaved changes.".arg(ConfigStore.path)
            type: Kirigami.MessageType.Warning
            visible: ConfigStore.changedOnDisk

            actions: [
                Kirigami.Action {
                    icon.name: "view-refresh"
                    text: "Reload and discard my changes"

                    onTriggered: ConfigStore.load()
                },
                Kirigami.Action {
                    icon.name: "document-edit"
                    text: "Keep my changes"

                    onTriggered: ConfigStore.keepEdits()
                }
            ]
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            position: Kirigami.InlineMessage.Position.Header
            // Values that do not fit the schema are shown as written; saving a corrected value clears the message.
            text: "Some values in the configuration file are not valid:\n"
                + ConfigStore.problems.map(problem => "• %1 → %2: %3".arg(problem.section).arg(problem.key).arg(problem.message)).join("\n")
            type: Kirigami.MessageType.Error
            visible: ConfigStore.problems.length > 0
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

            SectionHeading {
                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.largeSpacing
                Layout.rightMargin: Kirigami.Units.largeSpacing
                Layout.topMargin: Kirigami.Units.largeSpacing
                description: sectionView.info.description
                title: sectionView.info.title
            }
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Repeater {
                    model: ConfigSectionFilter {
                        section: sectionView.section
                        sourceModel: ConfigModel
                    }

                    // The rows only report edits; this page is what applies them to the store.
                    delegate: ConfigRow {
                        id: configRow

                        onEdited: value => ConfigStore.set(configRow.section, configRow.key, value)
                        onResetRequested: ConfigStore.reset(configRow.section, configRow.key)
                    }
                }
            }
            Item {
                Layout.fillHeight: true
            }
        }
    }
}
