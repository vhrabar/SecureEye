#include "Application.hpp"

#include <QIcon>
#include <QQmlContext>
#include <QQuickStyle>
#include <QUrl>

namespace {
constexpr auto kMainQml = "qrc:/qml/main.qml";
constexpr auto kAppIcon = ":/icons/logo.svg";
}

Application::Application(int &argc, char **argv): QGuiApplication(argc, argv){
    setApplicationName("SecureEye Manager");
    setOrganizationName("vhrabar");
    setOrganizationDomain("vhrabar.github.io");

    setDesktopFileName("secureeye-gui");
    QIcon::setFallbackThemeName("breeze");
    setWindowIcon(QIcon::fromTheme("secureeye", QIcon(QString::fromLatin1(kAppIcon))));

    if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE")) {
        QQuickStyle::setStyle("org.kde.desktop");
}
}

Application::~Application() = default;

auto Application::bootstrap() -> bool{
    createServices();
    exposeToQml();
    loadQml();

    return m_qmlLoaded;
}

void Application::createServices(){

}

void Application::exposeToQml(){
    m_engine.rootContext()->setContextProperty("appVersion", applicationVersion());
}

void Application::loadQml(){
    connect(&m_engine, &QQmlApplicationEngine::objectCreationFailed, this,
            [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);

    m_engine.load(QUrl(QString::fromLatin1(kMainQml)));
    m_qmlLoaded = !m_engine.rootObjects().isEmpty();
}
