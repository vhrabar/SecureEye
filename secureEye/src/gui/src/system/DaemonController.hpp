#ifndef SECUREEYE_DAEMONCONTROLLER_HPP
#define SECUREEYE_DAEMONCONTROLLER_HPP

#include <QObject>
#include <QQmlEngine>
#include <QString>
#include <QStringList>
#include <QVariantMap>

class QJSEngine;
class QTimer;

namespace secureEye {

// Status and start/stop/restart of secureeye-authd through systemd's D-Bus API.
// Reading the state needs no privileges. Controlling the unit goes through systemd's own polkit action
// (org.freedesktop.systemd1.manage-units), so this does not need pkexec or GuiBackend.
class DaemonController : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // systemd's ActiveState: "active", "inactive", "failed", "activating", "deactivating", "reloading", or
    // "unknown" when systemd could not be asked.
    Q_PROPERTY(QString activeState READ activeState NOTIFY stateChanged)
    // systemd's SubState, e.g. "running" or "dead".
    Q_PROPERTY(QString subState READ subState NOTIFY stateChanged)
    // Whether systemd knows the unit at all, i.e. the daemon is installed.
    Q_PROPERTY(bool installed READ isInstalled NOTIFY stateChanged)
    Q_PROPERTY(bool busy READ isBusy NOTIFY busyChanged)
    Q_PROPERTY(QString unitName READ unitName CONSTANT)

public:
    static auto instance() -> DaemonController*;
    static auto create(QQmlEngine* engine, QJSEngine* scriptEngine) -> DaemonController*;

    [[nodiscard]] auto activeState() const -> QString {
        return m_activeState;
    }
    [[nodiscard]] auto subState() const -> QString {
        return m_subState;
    }
    [[nodiscard]] auto isInstalled() const -> bool {
        return m_installed;
    }
    [[nodiscard]] auto isBusy() const -> bool {
        return m_busy;
    }
    [[nodiscard]] static auto unitName() -> QString;

    Q_INVOKABLE void start();
    Q_INVOKABLE void stop();
    Q_INVOKABLE void restart();
    Q_INVOKABLE void refresh();

signals:
    void stateChanged();
    void busyChanged();
    // A start/stop/restart was refused or failed. Cancelling the polkit prompt also ends up here.
    void failed(const QString& message);

private:
    // Private so QML has to use create(); see ConfigStore.
    explicit DaemonController(QObject* parent = nullptr);

    void control(const QString& method);
    void watchUnit(const QString& path);
    void applyProperties(const QVariantMap& properties);
    void setState(const QString& activeState, const QString& subState, bool installed);
    void setBusy(bool busy);

private slots:
    void onPropertiesChanged(const QString& interface, const QVariantMap& changed, const QStringList& invalidated);

private:
    QString m_unitPath;
    QString m_activeState = QStringLiteral("unknown");
    QString m_subState;
    bool m_installed = false;
    bool m_busy = false;
    QTimer* m_pollTimer = nullptr;
};

} // namespace secureEye

#endif // SECUREEYE_DAEMONCONTROLLER_HPP
