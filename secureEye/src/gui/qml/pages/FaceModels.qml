pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import SecureEye.Gui

// The current user's face models, managed through secureeye-authd.
Kirigami.ScrollablePage {
    id: page

    // The model a confirmation is pending for; -1 for "remove all".
    property int pendingModelId: -1
    property string pendingLabel

    title: "Face models"

    actions: [
        Kirigami.Action {
            enabled: !store.busy
            icon.name: "list-add"
            text: "Enroll"

            onTriggered: enrollDialog.open()
        },
        Kirigami.Action {
            enabled: store.count > 0
            icon.name: "media-playback-start"
            text: "Test"

            onTriggered: testDialog.open()
        },
        Kirigami.Action {
            // also the way out of an unreadable model file
            enabled: !store.busy && (store.count > 0 || store.error === "model_file_invalid")
            icon.name: "edit-delete"
            text: "Remove all"

            onTriggered: page.confirmRemove(-1, "")
        },
        Kirigami.Action {
            enabled: !store.loading
            icon.name: "view-refresh"
            text: "Reload"

            onTriggered: store.refresh()
        }
    ]

    function confirmRemove(modelId: int, label: string): void {
        page.pendingModelId = modelId;
        page.pendingLabel = label;
        removeDialog.open();
    }

    Component.onCompleted: store.refresh()

    ModelStore {
        id: store

        onOperationFailed: (code, message) => {
            operationMessage.text = message;
            operationMessage.visible = true;
        }
    }
    EnrollDialog {
        id: enrollDialog

        onEnrolled: store.refresh()
    }
    RecognitionTestDialog {
        id: testDialog
    }
    Kirigami.PromptDialog {
        id: removeDialog

        readonly property bool removesLast: page.pendingModelId < 0 || store.count === 1

        standardButtons: Kirigami.Dialog.NoButton
        subtitle: removeDialog.removesLast ? "Face login stops working for you until you enroll a new model." : "Your other face models are kept."
        title: page.pendingModelId < 0 ? "Remove all face models?" : "Remove \"%1\"?".arg(page.pendingLabel)

        customFooterActions: [
            Kirigami.Action {
                icon.name: "edit-delete"
                text: "Remove"

                onTriggered: {
                    removeDialog.close();
                    operationMessage.visible = false;
                    if (page.pendingModelId < 0) {
                        store.clear();
                    } else {
                        store.remove(page.pendingModelId);
                    }
                }
            },
            Kirigami.Action {
                icon.name: "dialog-cancel"
                text: "Cancel"

                onTriggered: removeDialog.close()
            }
        ]
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        SectionHeading {
            Layout.fillWidth: true
            description: "The face models used to recognize %1. Enroll several, for example with and without glasses, to make recognition more reliable.".arg(store.user)
            title: "Face models"
        }
        Kirigami.InlineMessage {
            id: operationMessage

            Layout.fillWidth: true
            showCloseButton: true
            type: Kirigami.MessageType.Error
        }

        Controls.BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            // only for the first load; reloads keep the cards on screen
            visible: store.loading && store.count === 0 && store.error === ""
        }

        // Could not load the list: daemon stopped, unreadable file, ...
        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            explanation: store.errorMessage
            icon.name: store.error === "daemon_unavailable" ? "network-disconnect" : "dialog-error"
            text: "Face models could not be loaded"
            visible: store.error !== "" && !store.loading

            helpfulAction: Kirigami.Action {
                icon.name: store.error === "model_file_invalid" ? "edit-delete" : "view-refresh"
                text: store.error === "model_file_invalid" ? "Remove all" : "Try again"

                onTriggered: {
                    if (store.error === "model_file_invalid") {
                        page.confirmRemove(-1, "");
                    } else {
                        store.refresh();
                    }
                }
            }
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            explanation: "Enroll your face to log in with SecureEye."
            icon.name: "user-identity"
            text: "No face models yet"
            visible: store.error === "" && !store.loading && store.count === 0

            helpfulAction: Kirigami.Action {
                icon.name: "list-add"
                text: "Enroll a face model"

                onTriggered: enrollDialog.open()
            }
        }

        Kirigami.CardsLayout {
            Layout.fillWidth: true
            visible: store.count > 0

            Repeater {
                model: store

                Kirigami.Card {
                    id: card

                    required property int modelId
                    required property string label
                    required property date created
                    required property string embeddingSpace

                    actions: [
                        Kirigami.Action {
                            enabled: !store.busy
                            icon.name: "edit-delete"
                            text: "Remove"

                            onTriggered: page.confirmRemove(card.modelId, card.label)
                        }
                    ]
                    banner {
                        titleIcon: "user-identity"
                        title: card.label
                    }
                    contentItem: ColumnLayout {
                        spacing: Kirigami.Units.smallSpacing

                        Controls.Label {
                            Layout.fillWidth: true
                            text: "Enrolled %1".arg(card.created.toLocaleString(Qt.locale(), Locale.ShortFormat))
                            wrapMode: Text.WordWrap
                        }
                        Controls.Label {
                            Layout.fillWidth: true
                            font.family: "monospace"
                            opacity: 0.5
                            text: "#%1 · %2".arg(card.modelId).arg(card.embeddingSpace)
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }
    }
}
