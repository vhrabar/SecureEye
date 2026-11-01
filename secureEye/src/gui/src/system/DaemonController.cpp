#include "DaemonController.hpp"

#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusError>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QPointer>
#include <QTimer>

namespace secureEye {
namespace {

constexpr auto kService = "org.freedesktop.systemd1";
constexpr auto kManagerPath = "/org/freedesktop/systemd1";
constexpr auto kManagerInterface = "org.freedesktop.systemd1.Manager";
constexpr auto kUnitInterface = "org.freedesktop.systemd1.Unit";
constexpr auto kPropertiesInterface = "org.freedesktop.DBus.Properties";

// Unit signals arrive within a second; the poll only catches what they cannot, like the unit being installed later.
constexpr int kPollIntervalMs = 5000;
// Long enough for the user to answer the polkit prompt.
constexpr int kControlTimeoutMs = 120000;

[[nodiscard]] auto bus() -> QDBusConnection {
    return QDBusConnection::systemBus();
}

[[nodiscard]] auto managerCall(const QString& method) -> QDBusMessage {
    return QDBusMessage::createMethodCall(QString::fromLatin1(kService), QString::fromLatin1(kManagerPath),
                                          QString::fromLatin1(kManagerInterface), method);
}

[[nodiscard]] auto controlErrorMessage(const QDBusError& error) -> QString {
    // Cancelling or failing the polkit prompt. QDBusError has no enum value for the second one.
    if (error.type() == QDBusError::AccessDenied ||
        error.name() == QLatin1String("org.freedesktop.DBus.Error.InteractiveAuthorizationRequired")) {
        return DaemonController::tr("You are not authorized to control the SecureEye daemon.");
    }
    if (error.type() == QDBusError::NoReply || error.type() == QDBusError::Timeout) {
        return DaemonController::tr("systemd did not answer in time.");
    }
    return error.message();
}

} // namespace

DaemonController::DaemonController(QObject* parent) : QObject(parent) {
    if (!bus().isConnected()) {
        return;
    }

    // Without a subscription systemd may not send unit change signals at all.
    bus().asyncCall(managerCall(QStringLiteral("Subscribe")));

    // LoadUnit returns a path even for a unit that is not installed; its LoadState then says "not-found".
    QDBusMessage load = managerCall(QStringLiteral("LoadUnit"));
    load << unitName();
    auto* watcher = new QDBusPendingCallWatcher(bus().asyncCall(load), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher* call) {
        call->deleteLater();
        const QDBusPendingReply<QDBusObjectPath> reply = *call;
        if (reply.isError()) {
            setState(QStringLiteral("unknown"), {}, false);
            return;
        }
        watchUnit(reply.value().path());
    });

    m_pollTimer = new QTimer(this);
    m_pollTimer->setInterval(kPollIntervalMs);
    connect(m_pollTimer, &QTimer::timeout, this, &DaemonController::refresh);
    m_pollTimer->start();
}

auto DaemonController::instance() -> DaemonController* {
    // Owned by the application, so it and its D-Bus connections go away before the event loop and the bus do.
    static QPointer<DaemonController> controller;
    if (controller == nullptr) {
        controller = new DaemonController(QCoreApplication::instance());
    }
    return controller;
}

auto DaemonController::create(QQmlEngine* /*engine*/, QJSEngine* /*scriptEngine*/) -> DaemonController* {
    DaemonController* const controller = instance();
    QJSEngine::setObjectOwnership(controller, QJSEngine::CppOwnership);

    return controller;
}

auto DaemonController::unitName() -> QString {
    return QStringLiteral("secureeye-authd.service");
}

void DaemonController::start() {
    control(QStringLiteral("StartUnit"));
}

void DaemonController::stop() {
    control(QStringLiteral("StopUnit"));
}

void DaemonController::restart() {
    control(QStringLiteral("RestartUnit"));
}

void DaemonController::control(const QString& method) {
    if (m_busy) {
        return;
    }

    QDBusMessage call = managerCall(method);
    call << unitName() << QStringLiteral("replace");
    // Lets systemd show a polkit prompt instead of refusing straight away.
    call.setInteractiveAuthorizationAllowed(true);

    setBusy(true);
    auto* watcher = new QDBusPendingCallWatcher(bus().asyncCall(call, kControlTimeoutMs), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher* pending) {
        pending->deleteLater();
        setBusy(false);

        // The reply only means the job was queued; the state itself arrives through the unit's signals.
        if (pending->isError()) {
            emit failed(controlErrorMessage(pending->error()));
        }
        refresh();
    });
}

void DaemonController::watchUnit(const QString& path) {
    m_unitPath = path;
    bus().connect(QString::fromLatin1(kService), m_unitPath, QString::fromLatin1(kPropertiesInterface),
                  QStringLiteral("PropertiesChanged"), this,
                  SLOT(onPropertiesChanged(QString, QVariantMap, QStringList)));
    refresh();
}

void DaemonController::refresh() {
    if (m_unitPath.isEmpty()) {
        return;
    }

    QDBusMessage getAll = QDBusMessage::createMethodCall(
        QString::fromLatin1(kService), m_unitPath, QString::fromLatin1(kPropertiesInterface), QStringLiteral("GetAll"));
    getAll << QString::fromLatin1(kUnitInterface);

    auto* watcher = new QDBusPendingCallWatcher(bus().asyncCall(getAll), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher* call) {
        call->deleteLater();
        const QDBusPendingReply<QVariantMap> reply = *call;
        if (reply.isError()) {
            setState(QStringLiteral("unknown"), {}, m_installed);
            return;
        }
        applyProperties(reply.value());
    });
}

void DaemonController::onPropertiesChanged(const QString& interface, const QVariantMap& changed,
                                           const QStringList& invalidated) {
    if (interface != QLatin1String(kUnitInterface)) {
        return;
    }

    // systemd sometimes only says a property changed without sending its value.
    if (!invalidated.isEmpty()) {
        refresh();
        return;
    }
    applyProperties(changed);
}

void DaemonController::applyProperties(const QVariantMap& properties) {
    const QString loadState = properties.value(QStringLiteral("LoadState")).toString();
    const bool installed = loadState.isEmpty() ? m_installed : loadState != QLatin1String("not-found");

    setState(properties.value(QStringLiteral("ActiveState"), m_activeState).toString(),
             properties.value(QStringLiteral("SubState"), m_subState).toString(), installed);
}

void DaemonController::setState(const QString& activeState, const QString& subState, const bool installed) {
    if (m_activeState == activeState && m_subState == subState && m_installed == installed) {
        return;
    }

    m_activeState = activeState;
    m_subState = subState;
    m_installed = installed;
    emit stateChanged();
}

void DaemonController::setBusy(const bool busy) {
    if (m_busy != busy) {
        m_busy = busy;
        emit busyChanged();
    }
}

} // namespace secureEye
