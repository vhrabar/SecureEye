#include "ConfigStore.hpp"

#include "system/GuiBackend.hpp"

#include <QDir>
#include <QFileInfo>
#include <QSaveFile>

#include <utility>

#ifndef SECUREEYE_CONFIG_PATH
#define SECUREEYE_CONFIG_PATH "/etc/secureEye/config.ini"
#endif

namespace secureEye {
namespace {

constexpr auto kPathOverrideEnv = "SECUREEYE_CONFIG";

[[nodiscard]] auto toView(const QByteArray& bytes) -> std::string_view {
    return {bytes.constData(), static_cast<std::size_t>(bytes.size())};
}

[[nodiscard]] auto toQString(const std::string_view view) -> QString {
    return QString::fromUtf8(view.data(), static_cast<qsizetype>(view.size()));
}

[[nodiscard]] auto findOption(const QString& section, const QString& key) -> const config::ConfigOption* {
    const QByteArray sectionUtf8 = section.toUtf8();
    const QByteArray keyUtf8 = key.toUtf8();

    return config::findOption(toView(sectionUtf8), toView(keyUtf8));
}

[[nodiscard]] auto configPath() -> QString {
    if (const QByteArray override = qgetenv(kPathOverrideEnv); !override.isEmpty()) {
        return QString::fromLocal8Bit(override);
    }

    return QStringLiteral(SECUREEYE_CONFIG_PATH);
}

} // namespace

ConfigStore::ConfigStore(QObject* parent) : QObject(parent), m_path(configPath()) {
    load();
}

auto ConfigStore::instance() -> ConfigStore* {
    static ConfigStore store;
    return &store;
}

auto ConfigStore::create(QQmlEngine* /*engine*/, QJSEngine* /*scriptEngine*/) -> ConfigStore* {
    ConfigStore* const store = instance();
    QJSEngine::setObjectOwnership(store, QJSEngine::CppOwnership);

    return store;
}

auto ConfigStore::isWritable() const -> bool {
    const QFileInfo info(m_path);

    return info.exists() ? info.isWritable() : QFileInfo(info.absolutePath()).isWritable();
}

auto ConfigStore::canSave() const -> bool {
    return isWritable() || (m_backend != nullptr && isInstalledConfig());
}

auto ConfigStore::isInstalledConfig() const -> bool {
    // `secureEye set` always edits the installed file, so it must not stand in for a SECUREEYE_CONFIG override.
    return QFileInfo(m_path).canonicalFilePath() ==
           QFileInfo(QStringLiteral(SECUREEYE_CONFIG_PATH)).canonicalFilePath();
}

void ConfigStore::setBackend(GuiBackend* backend) {
    if (m_backend != nullptr) {
        disconnect(m_backend, nullptr, this, nullptr);
    }
    m_backend = backend;

    if (m_backend != nullptr) {
        connect(m_backend, &GuiBackend::finished, this, [this](const int id) {
            if (id == m_saveJob) {
                finishSave(true, {});
            }
        });
        connect(m_backend, &GuiBackend::failed, this,
                [this](const int id, GuiBackend::Error /*error*/, const QString& /*code*/, const QString& message) {
                    if (id == m_saveJob) {
                        finishSave(false, message);
                    }
                });
    }

    emit writableChanged();
}

void ConfigStore::load() {
    const bool wasDirty = isDirty();
    m_pending.clear();

    QString error;
    if (!m_document.load(m_path, &error)) {
        emit loadFailed(error);
    }

    m_onDisk.clear();
    for (const config::ConfigOption& option : config::options()) {
        const QString section = toQString(option.section);
        const QString key = toQString(option.key);
        const QString mapKey = IniDocument::mapKey(section, key);

        const auto found = m_document.values().constFind(mapKey);
        const QString raw = found == m_document.values().constEnd() ? toQString(option.defaultValue) : *found;
        m_onDisk.insert(mapKey, canonical(option, raw));

        emit valueChanged(section, key);
    }

    if (wasDirty) {
        emit dirtyChanged();
    }
    emit writableChanged();
}

void ConfigStore::save() {
    if (isSaving()) {
        return;
    }

    if (!isDirty()) {
        emit saveFinished(true, {});
        return;
    }

    if (isWritable()) {
        writeDirectly();
    } else if (m_backend != nullptr && isInstalledConfig()) {
        writeThroughCli();
    } else {
        emit saveFinished(false, tr("%1 is not writable by this user, and only the installed configuration file "
                                    "can be saved with administrator privileges.")
                                     .arg(m_path));
    }
}

void ConfigStore::writeDirectly() {
    const QString contents = m_document.patched(m_pending);

    QSaveFile file(m_path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        emit saveFinished(false, file.errorString());
        return;
    }

    file.write(contents.toUtf8());
    if (!file.commit()) {
        emit saveFinished(false, file.errorString());
        return;
    }

    load();
    emit saveFinished(true, {});
}

void ConfigStore::writeThroughCli() {
    // `secureEye set` finds options by key alone. That is unambiguous because no key appears in two sections of
    // config.ini; the schema test for #31 should keep it that way.
    QStringList pairs;
    for (auto entry = m_pending.constBegin(); entry != m_pending.constEnd(); ++entry) {
        pairs << entry.key().mid(entry.key().indexOf(QLatin1Char('/')) + 1) << entry.value();
    }

    m_saveJob = m_backend->run(QStringLiteral("set"), pairs, GuiBackend::Privilege::Admin);
    emit savingChanged();
}

void ConfigStore::finishSave(const bool ok, const QString& error) {
    m_saveJob = 0;
    emit savingChanged();

    // Pending edits are kept on failure, so the user can retry or discard them.
    if (ok) {
        load();
    }
    emit saveFinished(ok, error);
}

void ConfigStore::revert() {
    if (!isDirty()) {
        return;
    }

    const IniDocument::ValueMap reverted = std::exchange(m_pending, {});
    for (auto entry = reverted.constBegin(); entry != reverted.constEnd(); ++entry) {
        const qsizetype separator = entry.key().indexOf(QLatin1Char('/'));
        emit valueChanged(entry.key().left(separator), entry.key().mid(separator + 1));
    }

    emit dirtyChanged();
}

QVariant ConfigStore::value(const QString& section, const QString& key) const {
    const config::ConfigOption* const option = findOption(section, key);
    if (option == nullptr) {
        return {};
    }

    return deserialize(*option, rawValue(*option));
}

void ConfigStore::set(const QString& section, const QString& key, const QVariant& value) {
    const config::ConfigOption* const option = findOption(section, key);
    if (option == nullptr) {
        return;
    }

    const QString mapKey = IniDocument::mapKey(section, key);
    const QString serialized = serialize(*option, value);
    if (serialized == rawValue(*option)) {
        return;
    }

    const bool wasDirty = isDirty();
    if (serialized == m_onDisk.value(mapKey)) {
        // Edited back to what is on disk, so it is no longer a pending change.
        m_pending.remove(mapKey);
    } else {
        m_pending.insert(mapKey, serialized);
    }

    emit valueChanged(section, key);
    if (wasDirty != isDirty()) {
        emit dirtyChanged();
    }
}

void ConfigStore::reset(const QString& section, const QString& key) {
    const config::ConfigOption* const option = findOption(section, key);
    if (option == nullptr) {
        return;
    }

    set(section, key, deserialize(*option, canonical(*option, toQString(option->defaultValue))));
}

bool ConfigStore::isModified(const QString& section, const QString& key) const {
    return m_pending.contains(IniDocument::mapKey(section, key));
}

auto ConfigStore::rawValue(const config::ConfigOption& option) const -> QString {
    const QString mapKey = IniDocument::mapKey(toQString(option.section), toQString(option.key));
    const auto pending = m_pending.constFind(mapKey);

    return pending == m_pending.constEnd() ? m_onDisk.value(mapKey) : *pending;
}

auto ConfigStore::canonical(const config::ConfigOption& option, const QString& raw) -> QString {
    return serialize(option, deserialize(option, raw));
}

auto ConfigStore::deserialize(const config::ConfigOption& option, const QString& raw) -> QVariant {
    switch (option.type) {
    case config::ValueType::Bool:
        return raw.compare(QLatin1String("true"), Qt::CaseInsensitive) == 0 || raw == QLatin1String("1") ||
               raw.compare(QLatin1String("yes"), Qt::CaseInsensitive) == 0;
    case config::ValueType::Int:
        return raw.toInt();
    case config::ValueType::Float:
        return raw.toDouble();
    case config::ValueType::String:
    case config::ValueType::Enum:
    case config::ValueType::Path:
    case config::ValueType::Multiline:
        break;
    }

    return raw;
}

auto ConfigStore::serialize(const config::ConfigOption& option, const QVariant& value) -> QString {
    switch (option.type) {
    case config::ValueType::Bool:
        return value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
    case config::ValueType::Int:
        return QString::number(value.toInt());
    case config::ValueType::Float:
        return QString::number(value.toDouble());
    case config::ValueType::String:
    case config::ValueType::Enum:
    case config::ValueType::Path:
    case config::ValueType::Multiline:
        break;
    }

    return value.toString();
}

} // namespace secureEye
