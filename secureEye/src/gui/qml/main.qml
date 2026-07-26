pragma ComponentBehavior: Bound
import QtQuick
import org.kde.kirigami as Kirigami
import "pages"

Kirigami.ApplicationWindow {
    id: root

    title: "SecureEye Manager"

    height: 900
    width: 1440

    pageStack.initialPage: Dashboard {

        id: dashboardPage
    }


    globalDrawer: Kirigami.GlobalDrawer {
        collapsible: true
        modal: false
        title: "SecureEye"
        titleIcon: "qrc:/icons/logo.svg"

        actions: [
            Kirigami.Action {
                checked: root.pageStack.currentItem === dashboardPage
                icon.source: "qrc:/icons/dot.svg"
                text: "Dashboard"

                onTriggered: root.pageStack.replace()
            }
        ]
    }
}
