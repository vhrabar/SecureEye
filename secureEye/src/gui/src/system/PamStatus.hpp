#ifndef SECUREEYE_PAMSTATUS_HPP
#define SECUREEYE_PAMSTATUS_HPP

#include <QObject>
#include <QQmlEngine>
#include <QString>

class QJSEngine;

namespace secureEye {

class GuiBackend;

// Whether face authentication is switched on, i.e. [core] disabled = false.
// Read from ConfigStore; switched with `secureEye disable` through GuiBackend, so it applies right away instead of
// waiting for the Configuration page's Save. The file watcher in ConfigStore then picks up the new value.
class PamStatus : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(bool enabled READ isEnabled NOTIFY enabledChanged)
    Q_PROPERTY(bool busy READ isBusy NOTIFY busyChanged)

public:
    static auto instance() -> PamStatus*;
    static auto create(QQmlEngine* engine, QJSEngine* scriptEngine) -> PamStatus*;

    [[nodiscard]] auto isEnabled() const -> bool;
    [[nodiscard]] auto isBusy() const -> bool {
        return m_job != 0;
    }

    void setBackend(GuiBackend* backend);

    Q_INVOKABLE void setEnabled(bool enabled);

signals:
    void enabledChanged();
    void busyChanged();
    void failed(const QString& message);

private:
    // Private so QML has to use create(); see ConfigStore.
    explicit PamStatus(QObject* parent = nullptr);

    void finish();

    GuiBackend* m_backend = nullptr;
    int m_job = 0;
};

} // namespace secureEye

#endif // SECUREEYE_PAMSTATUS_HPP
