#ifndef SECUREEYE_CONFIGSTORE_HPP
#define SECUREEYE_CONFIGSTORE_HPP

#include "ConfigSchema.hpp"
#include "IniDocument.hpp"

#include <QHash>
#include <QObject>
#include <QQmlEngine>
#include <QString>
#include <QVariant>

class QQmlEngine;
class QJSEngine;

namespace secureEye {

class GuiBackend;

// Holds the values of config.ini and the edits the user has made to them.
class ConfigStore : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

    Q_PROPERTY(bool dirty READ isDirty NOTIFY dirtyChanged)
    Q_PROPERTY(QString path READ path CONSTANT)
    Q_PROPERTY(bool writable READ isWritable NOTIFY writableChanged)
    Q_PROPERTY(bool canSave READ canSave NOTIFY writableChanged)
    Q_PROPERTY(bool saving READ isSaving NOTIFY savingChanged)

public:
    static auto instance() -> ConfigStore*;
    static auto create(QQmlEngine* engine, QJSEngine* scriptEngine) -> ConfigStore*;

    [[nodiscard]] auto path() const -> QString {
        return m_path;
    }
    [[nodiscard]] auto isDirty() const -> bool {
        return !m_pending.isEmpty();
    }
    // Whether this user can write the file directly.
    [[nodiscard]] auto isWritable() const -> bool;
    // Whether save() can succeed: directly, or through `secureEye set` when this is the installed config.ini.
    [[nodiscard]] auto canSave() const -> bool;
    [[nodiscard]] auto isSaving() const -> bool {
        return m_saveJob != 0;
    }

    // Lets save() fall back to the CLI through pkexec when the file is not writable.
    void setBackend(GuiBackend* backend);

    [[nodiscard]] Q_INVOKABLE QVariant value(const QString& section, const QString& key) const;
    Q_INVOKABLE void set(const QString& section, const QString& key, const QVariant& value);
    Q_INVOKABLE void reset(const QString& section, const QString& key);
    [[nodiscard]] Q_INVOKABLE bool isModified(const QString& section, const QString& key) const;

    Q_INVOKABLE void load();
    Q_INVOKABLE void save();
    Q_INVOKABLE void revert();

signals:
    void valueChanged(const QString& section, const QString& key);
    void dirtyChanged();
    void writableChanged();
    void savingChanged();
    void loadFailed(const QString& error);
    void saveFinished(bool ok, const QString& error);

private:
    // Private so QML has to use create(): with a public default constructor, QML_SINGLETON builds its own instance
    // and ignores create(), leaving QML and C++ with different objects.
    explicit ConfigStore(QObject* parent = nullptr);

    [[nodiscard]] static auto canonical(const config::ConfigOption& option, const QString& raw) -> QString;
    [[nodiscard]] static auto serialize(const config::ConfigOption& option, const QVariant& value) -> QString;
    [[nodiscard]] static auto deserialize(const config::ConfigOption& option, const QString& raw) -> QVariant;
    [[nodiscard]] auto rawValue(const config::ConfigOption& option) const -> QString;
    [[nodiscard]] auto isInstalledConfig() const -> bool;
    void writeDirectly();
    void writeThroughCli();
    void finishSave(bool ok, const QString& error);

    QString m_path;
    IniDocument m_document;
    IniDocument::ValueMap m_onDisk;
    IniDocument::ValueMap m_pending;
    GuiBackend* m_backend = nullptr;
    int m_saveJob = 0;
};

} // namespace secureEye

#endif // SECUREEYE_CONFIGSTORE_HPP
