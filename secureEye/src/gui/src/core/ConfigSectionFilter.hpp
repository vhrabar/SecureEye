#ifndef SECUREEYE_CONFIGSECTIONFILTER_HPP
#define SECUREEYE_CONFIGSECTIONFILTER_HPP

#include <QQmlEngine>
#include <QSortFilterProxyModel>

namespace secureEye {

// Narrows ConfigModel down to the options of one config.ini section, either the everyday ones or the advanced ones.
class ConfigSectionFilter : public QSortFilterProxyModel {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QString section READ section WRITE setSection NOTIFY sectionChanged)
    Q_PROPERTY(bool advanced READ advanced WRITE setAdvanced NOTIFY advancedChanged)

public:
    explicit ConfigSectionFilter(QObject* parent = nullptr);

    [[nodiscard]] auto section() const -> QString {
        return m_section;
    }
    void setSection(const QString& section);

    [[nodiscard]] auto advanced() const -> bool {
        return m_advanced;
    }
    void setAdvanced(bool advanced);

signals:
    void sectionChanged();
    void advancedChanged();

protected:
    [[nodiscard]] auto filterAcceptsRow(int sourceRow, const QModelIndex& sourceParent) const -> bool override;

private:
    void refilter();

    QString m_section;
    bool m_advanced = false;
};

} // namespace secureEye

#endif // SECUREEYE_CONFIGSECTIONFILTER_HPP
