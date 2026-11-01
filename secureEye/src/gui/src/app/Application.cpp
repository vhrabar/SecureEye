#include "Application.hpp"

#include "core/ConfigStore.hpp"
#include "system/PamStatus.hpp"

#include <QIcon>
#include <QQmlContext>
#include <QQuickStyle>
#include <QUrl>

namespace {

constexpr auto kQmlImportPath = "qrc:/qt/qml";
constexpr auto kMainQml = "qrc:/qt/qml/SecureEye/Gui/Main.qml";
constexpr auto kAppIcon = ":/icons/logo.svg";
constexpr auto kAppId = "io.github.vhrabar.SecureEye";
} // namespace

Application::Application(int& argc, char** argv) : QGuiApplication(argc, argv) {
    setApplicationName("secureeye-gui");
    setApplicationDisplayName("SecureEye");
    setApplicationVersion(QStringLiteral(SECUREEYE_VERSION));
    setOrganizationName("vhrabar");
    setOrganizationDomain("vhrabar.github.io");

    setDesktopFileName(QString::fromLatin1(kAppId));
    QIcon::setFallbackThemeName("breeze");
    setWindowIcon(QIcon::fromTheme(QString::fromLatin1(kAppId), QIcon(QString::fromLatin1(kAppIcon))));

    if (qEnvironmentVariableIsEmpty("QT_QUICK_CONTROLS_STYLE")) {
        QQuickStyle::setStyle("org.kde.desktop");
    }
}

Application::~Application() {
    secureEye::ConfigStore::instance()->setBackend(nullptr);
    secureEye::PamStatus::instance()->setBackend(nullptr);
}

auto Application::bootstrap() -> bool {
    createServices();
    exposeToQml();
    loadQml();

    return m_qmlLoaded;
}

void Application::createServices() {
    secureEye::ConfigStore::instance()->setBackend(&m_backend);
    secureEye::PamStatus::instance()->setBackend(&m_backend);

    // Built eagerly so that a config.ini that cannot be read reports itself
    // before any QML binding asks for a value.
    connect(secureEye::ConfigStore::instance(), &secureEye::ConfigStore::loadFailed, this,
            [](const QString& error) { qWarning("Could not read the configuration: %s", qPrintable(error)); });
}

void Application::exposeToQml() {
    m_engine.addImportPath(QString::fromLatin1(kQmlImportPath));
    m_engine.rootContext()->setContextProperty("appVersion", applicationVersion());
}

void Application::loadQml() {
    connect(
        &m_engine, &QQmlApplicationEngine::objectCreationFailed, this, [] { QCoreApplication::exit(1); },
        Qt::QueuedConnection);

    m_engine.load(QUrl(QString::fromLatin1(kMainQml)));
    m_qmlLoaded = !m_engine.rootObjects().isEmpty();
}
