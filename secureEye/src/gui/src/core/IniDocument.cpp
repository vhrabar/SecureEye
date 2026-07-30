#include "IniDocument.hpp"

#include <QFile>
#include <QMap>
#include <QRegularExpression>
#include <QTextStream>

namespace secureEye {
namespace {

// [section]
const QRegularExpression& sectionPattern() {
    static const QRegularExpression pattern(QStringLiteral(R"(^\s*\[([^\]]+)\]\s*$)"));
    return pattern;
}

// key = value, tolerating the ':' separator configparser also accepts.
const QRegularExpression& assignmentPattern() {
    static const QRegularExpression pattern(QStringLiteral(R"(^(\s*)([A-Za-z0-9_.\-]+)(\s*[=:]\s*)(.*)$)"));
    return pattern;
}

[[nodiscard]] auto isComment(const QString& line) -> bool {
    const QString trimmed = line.trimmed();
    return trimmed.startsWith(QLatin1Char('#')) || trimmed.startsWith(QLatin1Char(';'));
}

} // namespace

auto IniDocument::mapKey(const QString& section, const QString& key) -> QString {
    return section + QLatin1Char('/') + key;
}

auto IniDocument::load(const QString& path, QString* error) -> bool {
    m_lines.clear();
    m_values.clear();
    m_endsWithNewline = true;

    QFile file(path);
    if (!file.exists()) {
        return true;
    }

    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        if (error != nullptr) {
            *error = file.errorString();
        }
        return false;
    }

    const QString contents = QString::fromUtf8(file.readAll());
    file.close();

    m_endsWithNewline = contents.isEmpty() || contents.endsWith(QLatin1Char('\n'));

    QStringList rawLines = contents.split(QLatin1Char('\n'));
    // split() leaves a trailing empty element for a file ending in a newline.
    if (m_endsWithNewline && !rawLines.isEmpty()) {
        rawLines.removeLast();
    }

    QString section;
    for (const QString& raw : std::as_const(rawLines)) {
        Line line{.text = raw, .section = section, .key = {}};

        if (const auto sectionMatch = sectionPattern().match(raw); sectionMatch.hasMatch()) {
            section = sectionMatch.captured(1).trimmed();
            line.section = section;
        } else if (!isComment(raw)) {
            if (const auto assignment = assignmentPattern().match(raw); assignment.hasMatch()) {
                line.key = assignment.captured(2);
                // configparser does not strip inline comments by default, so the
                // whole remainder of the line is the value.
                m_values.insert(mapKey(section, line.key), assignment.captured(4).trimmed());
            }
        }

        m_lines.append(line);
    }

    return true;
}

auto IniDocument::patched(const ValueMap& changes) const -> QString {
    ValueMap pending = changes;
    QStringList out;
    out.reserve(m_lines.size() + pending.size() + 4);

    // Pass one: rewrite the values of keys that are already in the file.
    for (const Line& line : m_lines) {
        if (line.key.isEmpty()) {
            out.append(line.text);
            continue;
        }

        const QString key = mapKey(line.section, line.key);
        const auto pendingValue = pending.constFind(key);
        if (pendingValue == pending.constEnd()) {
            out.append(line.text);
            continue;
        }

        const auto assignment = assignmentPattern().match(line.text);
        out.append(assignment.captured(1) + assignment.captured(2) + assignment.captured(3) + *pendingValue);
        pending.erase(pending.constFind(key));
    }

    // Pass two: keys the file does not carry yet, appended to the end of their
    // section so they stay next to the options they belong with. Grouped by
    // section and applied in one rebuild, so the line indices taken from the
    // parsed document stay valid while inserting.
    QMap<QString, QStringList> additions;
    for (auto entry = pending.constBegin(); entry != pending.constEnd(); ++entry) {
        const qsizetype separator = entry.key().indexOf(QLatin1Char('/'));
        const QString section = entry.key().left(separator);
        const QString key = entry.key().mid(separator + 1);
        additions[section].append(key + QStringLiteral(" = ") + entry.value());
    }

    if (!additions.isEmpty()) {
        QMap<qsizetype, QStringList> insertions; // line index -> lines to insert before it
        QStringList appended;

        for (auto entry = additions.constBegin(); entry != additions.constEnd(); ++entry) {
            // Last line of the section, skipping the blank lines trailing it.
            qsizetype insertAt = -1;
            for (qsizetype index = 0; index < m_lines.size(); ++index) {
                if (m_lines.at(index).section == entry.key()) {
                    insertAt = index + 1;
                }
            }
            while (insertAt > 0 && out.at(insertAt - 1).trimmed().isEmpty()) {
                --insertAt;
            }

            if (insertAt < 0) {
                if (!appended.isEmpty() || (!out.isEmpty() && !out.constLast().trimmed().isEmpty())) {
                    appended.append(QString());
                }
                appended.append(QLatin1Char('[') + entry.key() + QLatin1Char(']'));
                appended.append(entry.value());
            } else {
                insertions[insertAt].append(entry.value());
            }
        }

        QStringList rebuilt;
        rebuilt.reserve(out.size() + pending.size() + appended.size());
        for (qsizetype index = 0; index < out.size(); ++index) {
            if (const auto insertion = insertions.constFind(index); insertion != insertions.constEnd()) {
                rebuilt.append(*insertion);
            }
            rebuilt.append(out.at(index));
        }
        if (const auto tail = insertions.constFind(out.size()); tail != insertions.constEnd()) {
            rebuilt.append(*tail);
        }
        rebuilt.append(appended);
        out = rebuilt;
    }

    QString text = out.join(QLatin1Char('\n'));
    if (m_endsWithNewline && !text.isEmpty()) {
        text.append(QLatin1Char('\n'));
    }

    return text;
}

} // namespace secureEye
