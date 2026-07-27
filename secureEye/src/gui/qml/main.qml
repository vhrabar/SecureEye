pragma ComponentBehavior: Bound
import QtQuick
import org.kde.kirigami as Kirigami
import "pages"

Kirigami.ApplicationWindow {
    id: root

    property Component currentPage: dashboardComponent

    title: "SecureEye Manager"

    height: 900
    width: 1440

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
                checked: root.currentPage === configComponent
                icon.name: "settings-configure"
                text: "Configuration"

                onTriggered: root.showPage(configComponent)
            }
        ]
    }

    Component {
        id: dashboardComponent

        Dashboard {}
    }
    Component {
        id: configComponent

        Configuration {}
    }

    // Swap the root of the page stack, dropping anything pushed on top of it.
    function showPage(page: Component) {
        if (root.currentPage === page) {
            return;
        }
        root.currentPage = page;
        root.pageStack.replace(page);
    }
}