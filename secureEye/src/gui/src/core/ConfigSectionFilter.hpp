#ifndef SECUREEYE_CONFIGSECTIONFILTER_HPP
#define SECUREEYE_CONFIGSECTIONFILTER_HPP

#include <QQmlEngine>
#include <QSortFilterProxyModel>

namespace secureEye {

// Narrows ConfigModel down to the options of one config.ini section,
class ConfigSectionFilter : public QSortFilterProxyModel {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QString section READ section WRITE setSection NOTIFY sectionChanged)

public:
    explicit ConfigSectionFilter(QObject* parent = nullptr);

    [[nodiscard]] auto section() const -> QString {
        return m_section;
    }
    void setSection(const QString& section);

signals:
    void sectionChanged();

protected:
    [[nodiscard]] auto filterAcceptsRow(int sourceRow, const QModelIndex& sourceParent) const -> bool override;

private:
    QString m_section;
};

} // namespace secureEye

#endif // SECUREEYE_CONFIGSECTIONFILTER_HPP
