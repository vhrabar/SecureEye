#include "core/ConfigSchema.hpp"
#include "core/ConfigStore.hpp"
#include "core/IniDocument.hpp"

#include <QFile>
#include <QSaveFile>
#include <QSet>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

using secureEye::ConfigStore;
using secureEye::IniDocument;

namespace {

const QSet<QString> kNotInSchema = {
    QStringLiteral("rubberstamps/enabled"),
    QStringLiteral("rubberstamps/stamp_rules"),
};

auto toQString(const std::string_view view) -> QString {
    return QString::fromUtf8(view.data(), static_cast<qsizetype>(view.size()));
}

auto readAll(const QString& path) -> QByteArray {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    return file.readAll();
}

// How editors and `secureEye set` write: a new file renamed over the old one.
void replaceFile(const QString& path, const QByteArray& contents) {
    QSaveFile file(path);
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write(contents);
    QVERIFY(file.commit());
}

void writeAll(const QString& path, const QByteArray& contents) {
    QFile file(path);
    QVERIFY(file.open(QIODevice::WriteOnly | QIODevice::Truncate));
    QCOMPARE(file.write(contents), contents.size());
}

auto problemKeys(const ConfigStore* store) -> QStringList {
    QStringList keys;
    for (const QVariant& problem : store->problems()) {
        const QVariantMap entry = problem.toMap();
        keys << IniDocument::mapKey(entry.value(QStringLiteral("section")).toString(),
                                    entry.value(QStringLiteral("key")).toString());
    }
    return keys;
}

} // namespace

class TestConfigStore : public QObject {
    Q_OBJECT

private slots:
    void initTestCase();
    void init();

    void schemaCoversShippedConfig();
    void noKeyInTwoSections();
    void untouchedDocumentRoundTripsByteIdentical();
    void saveRewritesOnlyTheEditedLine();
    void dirtyTrackingAndRevert();
    void shippedConfigHasNoProblems();
    void outOfRangeValueIsReportedNotClamped();
    void malformedValuesAreReported();
    void externalChangeReloadsWhenClean();
    void externalChangeWithUnsavedEditsAsksFirst();
    void keptEditsSaveOnTopOfExternalChange();
    void ownSaveIsNotAnExternalChange();

private:
    QTemporaryDir m_dir;
    QString m_path;
    QByteArray m_shipped;
    ConfigStore* m_store = nullptr;
};

void TestConfigStore::initTestCase() {
    QVERIFY(m_dir.isValid());
    m_shipped = readAll(QStringLiteral(SHIPPED_CONFIG_PATH));
    QVERIFY2(!m_shipped.isEmpty(), SHIPPED_CONFIG_PATH);

    // ConfigStore is a singleton that reads its path once, so point it at a scratch copy before first use.
    m_path = m_dir.filePath(QStringLiteral("config.ini"));
    writeAll(m_path, m_shipped);
    qputenv("SECUREEYE_CONFIG", m_path.toLocal8Bit());

    m_store = ConfigStore::instance();
    QCOMPARE(m_store->path(), m_path);
}

void TestConfigStore::init() {
    writeAll(m_path, m_shipped);
    m_store->revert();
    m_store->load();
}

void TestConfigStore::schemaCoversShippedConfig() {
    IniDocument document;
    QVERIFY(document.load(QStringLiteral(SHIPPED_CONFIG_PATH)));

    for (const auto& option : secureEye::config::options()) {
        const QString key = IniDocument::mapKey(toQString(option.section), toQString(option.key));
        QVERIFY2(document.values().contains(key), qPrintable(key + " is in the schema but not in config.ini"));
    }

    const QStringList fileKeys = document.values().keys();
    for (const QString& key : fileKeys) {
        if (kNotInSchema.contains(key)) {
            continue;
        }
        const qsizetype separator = key.indexOf(QLatin1Char('/'));
        const QByteArray section = key.left(separator).toUtf8();
        const QByteArray name = key.mid(separator + 1).toUtf8();
        QVERIFY2(secureEye::config::findOption(section.toStdString(), name.toStdString()) != nullptr,
                 qPrintable(key + " is in config.ini but not in ConfigSchema.hpp"));
    }
}

void TestConfigStore::noKeyInTwoSections() {
    // `secureEye set` finds options by key alone, which ConfigStore::save() relies on.
    IniDocument document;
    QVERIFY(document.load(QStringLiteral(SHIPPED_CONFIG_PATH)));

    QHash<QString, QString> sectionOf;
    const QStringList fileKeys = document.values().keys();
    for (const QString& key : fileKeys) {
        const qsizetype separator = key.indexOf(QLatin1Char('/'));
        const QString name = key.mid(separator + 1);
        const QString section = key.left(separator);
        QVERIFY2(!sectionOf.contains(name),
                 qPrintable(name + " is in both [" + sectionOf.value(name) + "] and [" + section + "]"));
        sectionOf.insert(name, section);
    }
}

void TestConfigStore::untouchedDocumentRoundTripsByteIdentical() {
    IniDocument document;
    QVERIFY(document.load(m_path));
    QCOMPARE(document.patched({}).toUtf8(), m_shipped);
}

void TestConfigStore::saveRewritesOnlyTheEditedLine() {
    const QString section = QStringLiteral("video");
    const QString key = QStringLiteral("certainty");
    m_store->set(section, key, 4.25);

    QSignalSpy finished(m_store, &ConfigStore::saveFinished);
    m_store->save();
    QCOMPARE(finished.count(), 1);
    QVERIFY2(finished.first().at(0).toBool(), qPrintable(finished.first().at(1).toString()));

    const QList<QByteArray> before = m_shipped.split('\n');
    const QList<QByteArray> after = readAll(m_path).split('\n');
    QCOMPARE(after.size(), before.size());

    QList<qsizetype> changed;
    for (qsizetype line = 0; line < before.size(); ++line) {
        if (before.at(line) != after.at(line)) {
            changed << line;
        }
    }
    QCOMPARE(changed.size(), 1);
    QCOMPARE(after.at(changed.first()), QByteArray("certainty = 4.25"));

    QVERIFY(!m_store->isDirty());
    QCOMPARE(m_store->value(section, key).toDouble(), 4.25);
}

void TestConfigStore::dirtyTrackingAndRevert() {
    const QString section = QStringLiteral("video");
    const QString key = QStringLiteral("timeout");
    const QVariant original = m_store->value(section, key);
    QSignalSpy dirtyChanged(m_store, &ConfigStore::dirtyChanged);

    QVERIFY(!m_store->isDirty());

    m_store->set(section, key, original.toInt() + 1);
    QVERIFY(m_store->isDirty());
    QVERIFY(m_store->isModified(section, key));
    QCOMPARE(dirtyChanged.count(), 1);

    // Editing back to the value on disk is no longer a pending change.
    m_store->set(section, key, original);
    QVERIFY(!m_store->isDirty());
    QVERIFY(!m_store->isModified(section, key));
    QCOMPARE(dirtyChanged.count(), 2);

    m_store->set(section, key, original.toInt() + 2);
    m_store->revert();
    QVERIFY(!m_store->isDirty());
    QCOMPARE(m_store->value(section, key), original);
    QCOMPARE(readAll(m_path), m_shipped);
}

void TestConfigStore::shippedConfigHasNoProblems() {
    QVERIFY2(m_store->problems().isEmpty(), qPrintable(problemKeys(m_store).join(QStringLiteral(", "))));
}

void TestConfigStore::outOfRangeValueIsReportedNotClamped() {
    QByteArray edited = m_shipped;
    edited.replace("certainty = 3.5", "certainty = 50");
    QVERIFY(edited != m_shipped);
    writeAll(m_path, edited);

    QSignalSpy problemsChanged(m_store, &ConfigStore::problemsChanged);
    m_store->load();

    QCOMPARE(problemsChanged.count(), 1);
    QCOMPARE(problemKeys(m_store), QStringList{QStringLiteral("video/certainty")});
    QCOMPARE(m_store->value(QStringLiteral("video"), QStringLiteral("certainty")).toDouble(), 50.0);
}

void TestConfigStore::malformedValuesAreReported() {
    QByteArray edited = m_shipped;
    edited.replace("timeout = 4", "timeout = soon");
    edited.replace("detection_notice = false", "detection_notice = maybe");
    writeAll(m_path, edited);

    m_store->load();

    const QStringList keys = problemKeys(m_store);
    QVERIFY2(keys.contains(QStringLiteral("video/timeout")), qPrintable(keys.join(QStringLiteral(", "))));
    QVERIFY2(keys.contains(QStringLiteral("core/detection_notice")), qPrintable(keys.join(QStringLiteral(", "))));
}

void TestConfigStore::externalChangeReloadsWhenClean() {
    QByteArray edited = m_shipped;
    edited.replace("timeout = 4", "timeout = 7");
    replaceFile(m_path, edited);

    QTRY_COMPARE(m_store->value(QStringLiteral("video"), QStringLiteral("timeout")).toInt(), 7);
    QVERIFY(!m_store->hasChangedOnDisk());

    // The file watch survives the rename, so a second change is seen too.
    edited.replace("timeout = 7", "timeout = 9");
    replaceFile(m_path, edited);
    QTRY_COMPARE(m_store->value(QStringLiteral("video"), QStringLiteral("timeout")).toInt(), 9);
}

void TestConfigStore::externalChangeWithUnsavedEditsAsksFirst() {
    m_store->set(QStringLiteral("video"), QStringLiteral("certainty"), 4.25);

    QByteArray edited = m_shipped;
    edited.replace("timeout = 4", "timeout = 7");
    replaceFile(m_path, edited);

    QTRY_VERIFY(m_store->hasChangedOnDisk());
    QVERIFY(m_store->isDirty());
    QCOMPARE(m_store->value(QStringLiteral("video"), QStringLiteral("certainty")).toDouble(), 4.25);
    QCOMPARE(m_store->value(QStringLiteral("video"), QStringLiteral("timeout")).toInt(), 4);

    // Reloading takes the new file and drops the edits.
    m_store->load();
    QVERIFY(!m_store->hasChangedOnDisk());
    QVERIFY(!m_store->isDirty());
    QCOMPARE(m_store->value(QStringLiteral("video"), QStringLiteral("timeout")).toInt(), 7);
}

void TestConfigStore::keptEditsSaveOnTopOfExternalChange() {
    m_store->set(QStringLiteral("video"), QStringLiteral("certainty"), 4.25);

    QByteArray edited = m_shipped;
    edited.replace("timeout = 4", "timeout = 7");
    replaceFile(m_path, edited);
    QTRY_VERIFY(m_store->hasChangedOnDisk());

    m_store->keepEdits();
    QVERIFY(!m_store->hasChangedOnDisk());
    m_store->save();

    const QByteArray saved = readAll(m_path);
    QVERIFY(saved.contains("certainty = 4.25"));
    QVERIFY2(saved.contains("timeout = 7"), "saving the kept edits undid the change made on disk");
}

void TestConfigStore::ownSaveIsNotAnExternalChange() {
    m_store->set(QStringLiteral("video"), QStringLiteral("certainty"), 4.25);
    m_store->set(QStringLiteral("video"), QStringLiteral("timeout"), 5);
    m_store->save();
    QVERIFY(!m_store->isDirty());

    // Give the watcher time to report the save, then make sure it was recognised as ours.
    m_store->set(QStringLiteral("video"), QStringLiteral("timeout"), 6);
    QTest::qWait(500);
    QVERIFY(!m_store->hasChangedOnDisk());
    QVERIFY(m_store->isDirty());
}

QTEST_GUILESS_MAIN(TestConfigStore)
#include "test_configstore.moc"
