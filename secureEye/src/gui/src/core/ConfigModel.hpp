#ifndef SECUREEYE_CONFIGMODEL_HPP
#define SECUREEYE_CONFIGMODEL_HPP

#include <QAbstractListModel>
#include <QQmlEngine>
#include <QVariantList>
#include <QVariantMap>

namespace secureEye {

class ConfigStore;

// The schema's ValueType, mirrored as an unscoped Q_ENUM so that QML delegates
// can switch on it as ConfigOptionType.Bool and friends.
class ConfigOptionType : public QObject {
    Q_OBJECT
    QML_ELEMENT
    QML_UNCREATABLE("ConfigOptionType only carries an enumeration")

public:
    enum Type : int {
        Bool,
        Int,
        Float,
        String,
        Enum,
        Path,
        Multiline,
    };
    Q_ENUM(Type)
};

// One row per entry of the compile time schema, so that the QML side never
// repeats what ConfigSchema.hpp already states.
//
// The model is read only towards QML: delegates render the roles and write
// through ConfigStore::set(). The store's valueChanged then comes back as
// dataChanged, which keeps a single direction of data flow and avoids the
// two-way binding loops a writable ValueRole invites.
class ConfigModel : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON

public:
    enum Role : int {
        SectionRole = Qt::UserRole,
        KeyRole,
        ValueTypeRole,
        LabelRole,
        HelpRole,
        NoteRole,
        ValueRole,
        DefaultValueRole,
        EnumValuesRole,
        EnumLabelsRole,
        HasRangeRole,
        MinimumRole,
        MaximumRole,
        ModifiedRole,
        ApplicableRole,
    };
    Q_ENUM(Role)

    explicit ConfigModel(QObject* parent = nullptr);

    static auto create(QQmlEngine* engine, QJSEngine* scriptEngine) -> ConfigModel*;

    [[nodiscard]] auto rowCount(const QModelIndex& parent = {}) const -> int override;
    [[nodiscard]] auto data(const QModelIndex& index, int role) const -> QVariant override;
    [[nodiscard]] auto roleNames() const -> QHash<int, QByteArray> override;

    // [{name, title, description}], in the order the schema declares them.
    // moc cannot parse trailing return types, so the invokables spell theirs out.
    [[nodiscard]] Q_INVOKABLE QVariantList sections() const;
    [[nodiscard]] Q_INVOKABLE QVariantMap sectionInfo(const QString& name) const;

private:
    void onValueChanged(const QString& section, const QString& key);

    ConfigStore* m_store;
};

} // namespace secureEye

#endif // SECUREEYE_CONFIGMODEL_HPP
