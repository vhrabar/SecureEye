#include "ConfigStore.hpp"

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
    if (!isDirty()) {
        emit saveFinished(true, {});
        return;
    }

    if (!isWritable()) {
        // TODO: route the write through authd (it already speaks over AUTHD_SOCKET_PATH) so that the GUI does not need
        // to run as root.
        emit saveFinished(false, tr("%1 is not writable by this user. Saving needs administrator "
                                    "privileges, which are not wired up yet.")
                                     .arg(m_path));
        return;
    }

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
