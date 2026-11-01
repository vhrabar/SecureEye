pragma ComponentBehavior: Bound
import QtQuick
import org.kde.kirigami as Kirigami
import SecureEye.Gui

Kirigami.ApplicationWindow {
    id: root

    property Component currentPage: dashboardComponent

    // Where to go once the unsaved changes prompt is answered.
    property Component pendingPage: null
    property bool pendingQuit: false
    // Set once the user agreed to quit, so onClosing lets it through.
    property bool quitConfirmed: false

    title: "SecureEye Manager"

    height: 900
    width: 1440

    // Must match currentPage, or the drawer checks one page while another is shown.
    pageStack.initialPage: dashboardComponent

    globalDrawer: Kirigami.GlobalDrawer {
        collapsible: true
        modal: false
        title: "SecureEye"
        titleIcon: "qrc:/icons/logo.svg"

        actions: [
            Kirigami.Action {
                checked: root.currentPage === dashboardComponent
                icon.name: "dashboard-show"
                text: "Dashboard"

                onTriggered: root.showPage(dashboardComponent)
            },
            Kirigami.Action {
                checked: root.currentPage === faceModelsComponent
                icon.name: "user-identity"
                text: "Face models"

                onTriggered: root.showPage(faceModelsComponent)
            },
            Kirigami.Action {
                checked: root.currentPage === configComponent
                icon.name: "settings-configure"
                text: "Configuration"

                onTriggered: root.showPage(configComponent)
            }
        ]
    }

    // Config changes affect login, so unsaved ones are never dropped or left behind silently.
    onClosing: close => {
        if (root.quitConfirmed || !ConfigStore.dirty) {
            return;
        }
        close.accepted = false;
        root.pendingPage = null;
        root.pendingQuit = true;
        unsavedDialog.open();
    }

    Component {
        id: dashboardComponent

        Dashboard {}
    }
    Component {
        id: faceModelsComponent

        FaceModels {}
    }
    Component {
        id: configComponent

        Configuration {}
    }

    Kirigami.PromptDialog {
        id: unsavedDialog

        standardButtons: Kirigami.Dialog.NoButton
        subtitle: "Your configuration changes have not been saved yet. They take effect at the next login only once they are saved."
        title: "Unsaved changes"

        customFooterActions: [
            Kirigami.Action {
                enabled: ConfigStore.canSave && !ConfigStore.saving
                icon.name: "document-save"
                text: "Save"

                onTriggered: {
                    unsavedDialog.close();
                    ConfigStore.save();
                }
            },
            Kirigami.Action {
                icon.name: "edit-delete"
                text: "Discard"

                onTriggered: {
                    unsavedDialog.close();
                    ConfigStore.revert();
                    root.continuePending();
                }
            },
            Kirigami.Action {
                icon.name: "dialog-cancel"
                text: "Cancel"

                onTriggered: unsavedDialog.close()
            }
        ]

        onRejected: root.clearPending()
    }

    Connections {
        // A save started from the prompt carries on to where the user was going once it succeeds. When it fails,
        // the user stays on the Configuration page, which shows the error.
        function onSaveFinished(ok: bool, error: string): void {
            if (ok) {
                root.continuePending();
            } else {
                root.clearPending();
            }
        }

        target: ConfigStore
    }

    // Swap the root of the page stack, dropping anything pushed on top of it.
    function showPage(page: Component): void {
        if (root.currentPage === page) {
            return;
        }
        if (root.currentPage === configComponent && ConfigStore.dirty) {
            root.pendingPage = page;
            root.pendingQuit = false;
            unsavedDialog.open();
            return;
        }
        root.currentPage = page;
        root.pageStack.replace(page);
    }

    function continuePending(): void {
        if (root.pendingQuit) {
            root.quitConfirmed = true;
            root.clearPending();
            root.close();
        } else if (root.pendingPage !== null) {
            const page = root.pendingPage;
            root.clearPending();
            root.showPage(page);
        }
    }

    function clearPending(): void {
        root.pendingPage = null;
        root.pendingQuit = false;
    }
}
