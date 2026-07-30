#ifndef SECUREEYE_INIDOCUMENT_HPP
#define SECUREEYE_INIDOCUMENT_HPP

#include <QHash>
#include <QString>
#include <QStringList>

namespace secureEye {

// A line oriented view of config.ini.
class IniDocument {
public:
    // "section/key" -> value, matching the keys ConfigStore hands around.
    using ValueMap = QHash<QString, QString>;

    [[nodiscard]] static auto mapKey(const QString& section, const QString& key) -> QString;

    auto load(const QString& path, QString* error = nullptr) -> bool;

    [[nodiscard]] auto values() const -> const ValueMap& {
        return m_values;
    }

    [[nodiscard]] auto patched(const ValueMap& changes) const -> QString;

private:
    struct Line {
        QString text;
        QString section;
        QString key;
    };

    QList<Line> m_lines;
    ValueMap m_values;
    bool m_endsWithNewline = true;
};

} // namespace secureEye

#endif // SECUREEYE_INIDOCUMENT_HPP
