#include "FakeAuthd.hpp"
#include "system/ModelStore.hpp"

#include <QJsonArray>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

using secureEye::ModelStore;
using secureEye::testing::FakeDaemon;
using secureEye::testing::kWaitMs;

namespace {

auto model(const int id, const QString& label) -> QJsonObject {
    return {{QStringLiteral("id"), id},
            {QStringLiteral("label"), label},
            {QStringLiteral("time"), 1700000000 + id},
            {QStringLiteral("model_id"), QStringLiteral("dlib-resnet-v1")}};
}

auto result(const QString& result, const QJsonObject& data = {}) -> QJsonObject {
    QJsonObject message{{QStringLiteral("type"), QStringLiteral("result")}, {QStringLiteral("result"), result}};
    if (!data.isEmpty()) {
        message.insert(QStringLiteral("data"), data);
    }
    return message;
}

auto listing(const QJsonArray& models) -> QJsonObject {
    return result(QStringLiteral("success"), {{QStringLiteral("models"), models}});
}

// Answers the next request with message; returns the request.
auto answer(FakeDaemon& daemon, const QJsonObject& message) -> QJsonObject {
    const QJsonObject request = daemon.accept();
    daemon.send(message, request.value(QStringLiteral("request_id")).toString());
    return request;
}

} // namespace

class TestModelStore : public QObject {
    Q_OBJECT

private slots:
    void init() {
        QVERIFY(m_dir.isValid());
        m_path = m_dir.filePath(QStringLiteral("authd.sock"));
        qputenv("SECUREEYE_AUTHD_SOCKET", m_path.toLocal8Bit());
    }

    void refreshFillsTheRows() {
        FakeDaemon daemon(m_path);
        ModelStore store;
        QSignalSpy loading(&store, &ModelStore::loadingChanged);
        store.refresh();
        QVERIFY(store.isLoading());

        const QJsonObject request =
            answer(daemon, listing({model(0, QStringLiteral("desk")), model(2, QStringLiteral("window"))}));

        QCOMPARE(request.value(QStringLiteral("type")).toString(), QStringLiteral("models_list"));
        QTRY_VERIFY_WITH_TIMEOUT(!store.isLoading(), kWaitMs);
        QCOMPARE(store.count(), 2);
        QCOMPARE(store.rowCount(), 2);
        const QModelIndex second = store.index(1);
        QCOMPARE(store.data(second, ModelStore::ModelIdRole).toInt(), 2);
        QCOMPARE(store.data(second, ModelStore::LabelRole).toString(), QStringLiteral("window"));
        QCOMPARE(store.data(second, ModelStore::CreatedRole).toDateTime(), QDateTime::fromSecsSinceEpoch(1700000002));
        QCOMPARE(store.data(second, ModelStore::EmbeddingSpaceRole).toString(), QStringLiteral("dlib-resnet-v1"));
        QVERIFY(store.error().isEmpty());
        QCOMPARE(loading.count(), 2);
        QVERIFY(store.roleNames().values().contains("modelId"));
        // the daemon numbers new models after the last one, gaps and all
        QCOMPARE(store.nextModelId(), 3);
    }

    void nextModelIdWithoutModels() {
        ModelStore store;
        QCOMPARE(store.nextModelId(), 0);
    }

    void noModelsIsAnEmptyListNotAnError() {
        FakeDaemon daemon(m_path);
        ModelStore store;
        store.refresh();

        answer(daemon, listing({}));

        QTRY_VERIFY_WITH_TIMEOUT(!store.isLoading(), kWaitMs);
        QCOMPARE(store.count(), 0);
        QVERIFY(store.error().isEmpty());
    }

    void stoppedDaemonIsItsOwnState() {
        ModelStore store;
        QSignalSpy errors(&store, &ModelStore::errorChanged);
        store.refresh();

        QVERIFY(errors.wait(kWaitMs));
        QCOMPARE(store.error(), QStringLiteral("daemon_unavailable"));
        QVERIFY(!store.errorMessage().isEmpty());
        QVERIFY(!store.isLoading());
    }

    void unreadableFileEmptiesTheListAndCanBeCleared() {
        FakeDaemon daemon(m_path);
        ModelStore store;
        store.refresh();
        answer(daemon, listing({model(0, QStringLiteral("desk"))}));
        QTRY_COMPARE_WITH_TIMEOUT(store.count(), 1, kWaitMs);

        store.refresh();
        answer(daemon, result(QStringLiteral("model_file_invalid")));
        QTRY_COMPARE_WITH_TIMEOUT(store.error(), QStringLiteral("model_file_invalid"), kWaitMs);
        QCOMPARE(store.count(), 0);

        QVERIFY(store.clear());
        const QJsonObject clear = answer(daemon, result(QStringLiteral("success")));
        QCOMPARE(clear.value(QStringLiteral("type")).toString(), QStringLiteral("models_clear"));
        answer(daemon, listing({}));
        QTRY_VERIFY_WITH_TIMEOUT(store.error().isEmpty(), kWaitMs);
    }

    void removeReloadsTheList() {
        FakeDaemon daemon(m_path);
        ModelStore store;
        QSignalSpy busy(&store, &ModelStore::busyChanged);
        QSignalSpy failed(&store, &ModelStore::operationFailed);

        QVERIFY(store.remove(3));
        QVERIFY(store.isBusy());
        const QJsonObject remove =
            answer(daemon, result(QStringLiteral("success"),
                                  {{QStringLiteral("removed"), 3}, {QStringLiteral("remaining"), 1}}));
        QCOMPARE(remove.value(QStringLiteral("type")).toString(), QStringLiteral("models_remove"));
        QCOMPARE(remove.value(QStringLiteral("model")).toInt(), 3);

        // the reload that follows every change
        const QJsonObject reload = answer(daemon, listing({model(0, QStringLiteral("desk"))}));
        QCOMPARE(reload.value(QStringLiteral("type")).toString(), QStringLiteral("models_list"));
        QTRY_COMPARE_WITH_TIMEOUT(store.count(), 1, kWaitMs);
        QVERIFY(!store.isBusy());
        QCOMPARE(busy.count(), 2);
        QCOMPARE(failed.count(), 0);
    }

    void failedRemoveIsReportedAndStillReloads() {
        FakeDaemon daemon(m_path);
        ModelStore store;
        QSignalSpy failed(&store, &ModelStore::operationFailed);

        QVERIFY(store.remove(7));
        answer(daemon, result(QStringLiteral("model_not_found")));
        answer(daemon, listing({}));

        QTRY_COMPARE_WITH_TIMEOUT(failed.count(), 1, kWaitMs);
        QCOMPARE(failed.at(0).at(0).toString(), QStringLiteral("model_not_found"));
        QVERIFY(!failed.at(0).at(1).toString().isEmpty());
        QTRY_VERIFY_WITH_TIMEOUT(!store.isLoading(), kWaitMs);
    }

    void oneChangeAtATime() {
        FakeDaemon daemon(m_path);
        ModelStore store;

        QVERIFY(store.remove(1));
        QVERIFY(!store.remove(2));
        QVERIFY(!store.clear());

        const QJsonObject remove = answer(daemon, result(QStringLiteral("success")));
        QCOMPARE(remove.value(QStringLiteral("model")).toInt(), 1);
    }

    void newRefreshDropsTheRunningOne() {
        FakeDaemon daemon(m_path);
        ModelStore store;
        QSignalSpy loading(&store, &ModelStore::loadingChanged);
        store.refresh();
        daemon.accept();
        QLocalSocket* first = daemon.connection();

        store.refresh();

        // the first connection is closed, which is how the daemon learns nobody waits for it
        QVERIFY(first->state() == QLocalSocket::UnconnectedState || first->waitForDisconnected(kWaitMs));
        answer(daemon, listing({model(0, QStringLiteral("desk"))}));
        QTRY_VERIFY_WITH_TIMEOUT(!store.isLoading(), kWaitMs);
        QCOMPARE(store.count(), 1);
    }

private:
    QTemporaryDir m_dir;
    QString m_path;
};

QTEST_GUILESS_MAIN(TestModelStore)
#include "test_modelstore.moc"
