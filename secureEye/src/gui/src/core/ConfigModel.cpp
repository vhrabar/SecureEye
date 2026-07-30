#include "ConfigModel.hpp"

#include "ConfigSchema.hpp"
#include "ConfigStore.hpp"

namespace secureEye {
namespace {

[[nodiscard]] auto toQString(const std::string_view view) -> QString {
    return QString::fromUtf8(view.data(), static_cast<qsizetype>(view.size()));
}

[[nodiscard]] auto toStringList(const std::span<const std::string_view> views) -> QStringList {
    QStringList list;
    list.reserve(static_cast<qsizetype>(views.size()));
    for (const std::string_view view : views) {
        list.append(toQString(view));
    }

    return list;
}

static_assert(static_cast<int>(config::ValueType::Bool) == ConfigOptionType::Bool);
static_assert(static_cast<int>(config::ValueType::Multiline) == ConfigOptionType::Multiline);

} // namespace

ConfigModel::ConfigModel(QObject* parent) : QAbstractListModel(parent), m_store(ConfigStore::instance()) {
    connect(m_store, &ConfigStore::valueChanged, this, &ConfigModel::onValueChanged);
}

auto ConfigModel::create(QQmlEngine* /*engine*/, QJSEngine* /*scriptEngine*/) -> ConfigModel* {
    static ConfigModel model;
    QJSEngine::setObjectOwnership(&model, QJSEngine::CppOwnership);

    return &model;
}

auto ConfigModel::rowCount(const QModelIndex& parent) const -> int {
    return parent.isValid() ? 0 : static_cast<int>(config::options().size());
}

auto ConfigModel::data(const QModelIndex& index, const int role) const -> QVariant {
    if (!index.isValid() || index.row() >= rowCount()) {
        return {};
    }

    const config::ConfigOption& option = config::options()[static_cast<std::size_t>(index.row())];
    const QString section = toQString(option.section);
    const QString key = toQString(option.key);

    switch (role) {
    case SectionRole:
        return section;
    case KeyRole:
        return key;
    case ValueTypeRole:
        return static_cast<int>(option.type);
    case LabelRole:
        return toQString(option.label);
    case HelpRole:
        return toQString(option.help);
    case NoteRole:
        return toQString(option.note);
    case ValueRole:
        return m_store->value(section, key);
    case DefaultValueRole:
        return toQString(option.defaultValue);
    case EnumValuesRole:
        return toStringList(option.enumValues);
    case EnumLabelsRole:
        return toStringList(option.enumLabels.empty() ? option.enumValues : option.enumLabels);
    case HasRangeRole:
        return option.hasRange;
    case MinimumRole:
        return option.min;
    case MaximumRole:
        return option.max;
    case ModifiedRole:
        return m_store->isModified(section, key);
    case ApplicableRole: {
        if (option.requiresKey.empty()) {
            return true;
        }

        return m_store->value(section, toQString(option.requiresKey)).toString() == toQString(option.requiresValue);
    }
    default:
        return {};
    }
}

auto ConfigModel::roleNames() const -> QHash<int, QByteArray> {
    return {
        {SectionRole, "section"},
        {KeyRole, "key"},
        {ValueTypeRole, "valueType"},
        {LabelRole, "label"},
        {HelpRole, "help"},
        {NoteRole, "note"},
        {ValueRole, "value"},
        {DefaultValueRole, "defaultValue"},
        {EnumValuesRole, "enumValues"},
        {EnumLabelsRole, "enumLabels"},
        {HasRangeRole, "hasRange"},
        {MinimumRole, "minimum"},
        {MaximumRole, "maximum"},
        {ModifiedRole, "modified"},
        {ApplicableRole, "applicable"},
    };
}

QVariantList ConfigModel::sections() const {
    QVariantList list;
    list.reserve(static_cast<qsizetype>(config::sections().size()));
    for (const config::ConfigSectionInfo& info : config::sections()) {
        list.append(sectionInfo(toQString(info.name)));
    }

    return list;
}

QVariantMap ConfigModel::sectionInfo(const QString& name) const {
    const QByteArray nameUtf8 = name.toUtf8();
    const config::ConfigSectionInfo* const info =
        config::findSection({nameUtf8.constData(), static_cast<std::size_t>(nameUtf8.size())});
    if (info == nullptr) {
        return {};
    }

    return {
        {QStringLiteral("name"), toQString(info->name)},
        {QStringLiteral("title"), toQString(info->title)},
        {QStringLiteral("description"), toQString(info->description)},
    };
}

void ConfigModel::onValueChanged(const QString& section, const QString& key) {
    const std::span<const config::ConfigOption> options = config::options();

    for (int row = 0; row < static_cast<int>(options.size()); ++row) {
        const config::ConfigOption& option = options[static_cast<std::size_t>(row)];
        const bool isOption = toQString(option.section) == section && toQString(option.key) == key;
        // Options gated on this key change their applicability with it.
        const bool dependsOnOption =
            !option.requiresKey.empty() && toQString(option.section) == section && toQString(option.requiresKey) == key;

        if (isOption || dependsOnOption) {
            const QModelIndex changed = index(row);
            emit dataChanged(changed, changed, {ValueRole, ModifiedRole, ApplicableRole});
        }
    }
}

} // namespace secureEye
