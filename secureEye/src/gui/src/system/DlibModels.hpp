#ifndef SECUREEYE_DLIBMODELS_HPP
#define SECUREEYE_DLIBMODELS_HPP

#include <QObject>
#include <QQmlEngine>
#include <QString>

class QJSEngine;

namespace secureEye {

class GuiBackend;

// The data files the dlib backend needs. Packages do not ship them, so they are fetched with
// `secureEye fetch-models` through GuiBackend (pkexec). Presence is checked on disk: the directory is world-readable.
class DlibModels : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    // [core] detector_backend is dlib
    Q_PROPERTY(bool required READ isRequired NOTIFY requiredChanged)
    // All data files are in the data directory
    Q_PROPERTY(bool present READ isPresent NOTIFY presentChanged)
    Q_PROPERTY(bool busy READ isBusy NOTIFY busyChanged)
    // Only worth offering the download when dlib is selected and something is missing.
    Q_PROPERTY(bool canFetch READ canFetch NOTIFY canFetchChanged)
    Q_PROPERTY(QString directory READ directory CONSTANT)

public:
    static auto instance() -> DlibModels*;
    static auto create(QQmlEngine* engine, QJSEngine* scriptEngine) -> DlibModels*;

    [[nodiscard]] auto isRequired() const -> bool;
    [[nodiscard]] auto isPresent() const -> bool {
        return m_present;
    }
    [[nodiscard]] auto isBusy() const -> bool {
        return m_job != 0;
    }
    [[nodiscard]] auto canFetch() const -> bool {
        return isRequired() && !m_present && !isBusy();
    }
    [[nodiscard]] static auto directory() -> QString;

    void setBackend(GuiBackend* backend);

    Q_INVOKABLE void fetch();
    // Checks the data directory again, e.g. after the files were fetched from a terminal.
    Q_INVOKABLE void refresh();

signals:
    void requiredChanged();
    void presentChanged();
    void busyChanged();
    void canFetchChanged();
    void fetched();
    void failed(const QString& message);

private:
    // Private so QML has to use create(); see ConfigStore.
    explicit DlibModels(QObject* parent = nullptr);

    void finish();

    GuiBackend* m_backend = nullptr;
    int m_job = 0;
    bool m_present = false;
};

} // namespace secureEye

#endif // SECUREEYE_DLIBMODELS_HPP
