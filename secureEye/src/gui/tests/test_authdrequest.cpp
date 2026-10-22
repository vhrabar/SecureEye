#include "system/AuthdRequest.hpp"

#include <QBuffer>
#include <QDeadlineTimer>
#include <QJsonDocument>
#include <QLocalServer>
#include <QLocalSocket>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>
#include <QtEndian>

#include <memory>

using secureEye::AuthdRequest;

namespace {

constexpr int kWaitMs = 3000;

// The daemon's side of one connection, driven synchronously from the test.
class FakeDaemon {
public:
    explicit FakeDaemon(const QString& path) {
        QLocalServer::removeServer(path);
        QVERIFY(m_server.listen(path));
    }

    // Waits for the client and returns its request.
    auto accept() -> QJsonObject {
        // the client connects from its event loop, so spin it rather than block in waitForNewConnection()
        QDeadlineTimer deadline(kWaitMs);
        while (!m_server.hasPendingConnections() && !deadline.hasExpired()) {
            QTest::qWait(10);
        }
        if (!m_server.hasPendingConnections()) {
            return {};
        }
        m_conn.reset(m_server.nextPendingConnection());
        return read();
    }

    auto read() -> QJsonObject {
        if (!m_conn) {
            return {};
        }
        while (m_buffer.size() < 4 || m_buffer.size() < 4 + qFromBigEndian<quint32>(m_buffer.constData())) {
            // the client writes from its event loop, so keep it spinning while we wait
            if (!m_conn->bytesAvailable()) {
                QTest::qWait(10);
                if (m_conn->state() != QLocalSocket::ConnectedState && !m_conn->bytesAvailable()) {
                    return {};
                }
            }
            m_buffer += m_conn->readAll();
        }
        const auto length = qFromBigEndian<quint32>(m_buffer.constData());
        const QByteArray body = m_buffer.mid(4, length);
        m_buffer.remove(0, 4 + length);
        return QJsonDocument::fromJson(body).object();
    }

    void sendRaw(const QByteArray& body) {
        QByteArray frame(4, Qt::Uninitialized);
        qToBigEndian<quint32>(static_cast<quint32>(body.size()), frame.data());
        m_conn->write(frame + body);
        m_conn->flush();
    }

    void send(QJsonObject message, const QString& requestId) {
        message.insert(QStringLiteral("v"), 2);
        message.insert(QStringLiteral("request_id"), requestId);
        sendRaw(QJsonDocument(message).toJson(QJsonDocument::Compact));
    }

    auto connection() -> QLocalSocket* {
        return m_conn.get();
    }

private:
    QLocalServer m_server;
    std::unique_ptr<QLocalSocket> m_conn;
    QByteArray m_buffer;
};

auto jpeg() -> QByteArray {
    QImage image(32, 24, QImage::Format_RGB888);
    image.fill(Qt::darkGreen);
    QByteArray bytes;
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::WriteOnly);
    image.save(&buffer, "JPEG");
    return bytes;
}

} // namespace

class TestAuthdRequest : public QObject {
    Q_OBJECT

private slots:
    void init() {
        QVERIFY(m_dir.isValid());
        m_path = m_dir.filePath(QStringLiteral("authd.sock"));
        qputenv("SECUREEYE_AUTHD_SOCKET", m_path.toLocal8Bit());
    }

    void sendsRequestAndReportsResult() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsRemove(3, this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();

        const QJsonObject sent = daemon.accept();
        QCOMPARE(sent.value(QStringLiteral("v")).toInt(), 2);
        QCOMPARE(sent.value(QStringLiteral("type")).toString(), QStringLiteral("models_remove"));
        QCOMPARE(sent.value(QStringLiteral("model")).toInt(), 3);
        QCOMPARE(sent.value(QStringLiteral("username")).toString(), AuthdRequest::currentUser());
        QCOMPARE(sent.value(QStringLiteral("request_id")).toString(), request->requestId());

        daemon.send({{QStringLiteral("type"), QStringLiteral("result")},
                     {QStringLiteral("result"), QStringLiteral("success")},
                     {QStringLiteral("data"), QJsonObject{{QStringLiteral("remaining"), 1}}}},
                    request->requestId());

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.count(), 1);
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("success"));
        QCOMPARE(finished.at(0).at(1).toJsonObject().value(QStringLiteral("remaining")).toInt(), 1);
        QCOMPARE(request->state(), AuthdRequest::State::Finished);
    }

    void enrollRequestFields() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::enroll(QStringLiteral("desk"), true, true, this);
        request->start();

        const QJsonObject sent = daemon.accept();
        QCOMPARE(sent.value(QStringLiteral("type")).toString(), QStringLiteral("enroll"));
        QCOMPARE(sent.value(QStringLiteral("label")).toString(), QStringLiteral("desk"));
        QVERIFY(sent.value(QStringLiteral("replace")).toBool());
        QVERIFY(sent.value(QStringLiteral("preview")).toBool());
    }

    void streamsFramesWithPreviews() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::test(5000, true, this);
        QSignalSpy started(request, &AuthdRequest::started);
        QSignalSpy frames(request, &AuthdRequest::frameReceived);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        const QString id = request->requestId();
        daemon.send({{QStringLiteral("type"), QStringLiteral("started")}}, id);
        const QJsonObject report{{QStringLiteral("state"), QStringLiteral("match")}, {QStringLiteral("distance"), 2.5}};
        daemon.send({{QStringLiteral("type"), QStringLiteral("frame")},
                     {QStringLiteral("report"), report},
                     {QStringLiteral("preview"), QString::fromLatin1(jpeg().toBase64())}},
                    id);
        daemon.send({{QStringLiteral("type"), QStringLiteral("frame")}, {QStringLiteral("report"), report}}, id);
        daemon.send({{QStringLiteral("type"), QStringLiteral("result")},
                     {QStringLiteral("result"), QStringLiteral("completed")}},
                    id);

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(started.count(), 1);
        QCOMPARE(frames.count(), 2);
        QCOMPARE(frames.at(0).at(0).toJsonObject().value(QStringLiteral("distance")).toDouble(), 2.5);
        const auto preview = frames.at(0).at(1).value<QImage>();
        QCOMPARE(preview.size(), QSize(32, 24));
        QVERIFY(frames.at(1).at(1).value<QImage>().isNull());
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("completed"));
    }

    void cancelWhileRunningAsksTheDaemon() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::test(60000, false, this);
        QSignalSpy started(request, &AuthdRequest::started);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();
        daemon.send({{QStringLiteral("type"), QStringLiteral("started")}}, request->requestId());
        QVERIFY(started.wait(kWaitMs));

        request->cancel();

        const QJsonObject cancel = daemon.read();
        QCOMPARE(cancel.value(QStringLiteral("type")).toString(), QStringLiteral("cancel"));
        QCOMPARE(finished.count(), 0);
        daemon.send({{QStringLiteral("type"), QStringLiteral("result")},
                     {QStringLiteral("result"), QStringLiteral("cancelled")}},
                    request->requestId());
        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("cancelled"));
    }

    void cancelBeforeStartFinishesLocally() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::enroll(QStringLiteral("desk"), false, false, this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        request->cancel();

        QCOMPARE(finished.count(), 1);
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("cancelled"));
        // the connection is closed, which is what makes the daemon give the camera back
        QVERIFY(daemon.connection()->waitForDisconnected(kWaitMs));
    }

    void destroyingTheRequestClosesTheConnection() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::test(60000, false, this);
        request->start();
        daemon.accept();

        delete request;

        QVERIFY(daemon.connection()->waitForDisconnected(kWaitMs));
    }

    void daemonNotRunning() {
        auto* request = AuthdRequest::modelsList(this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        // never synchronous, even though the socket does not exist
        QCOMPARE(finished.count(), 0);

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("daemon_unavailable"));
    }

    void connectionLostBeforeResult() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsList(this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        daemon.connection()->disconnectFromServer();

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.count(), 1);
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("connection_lost"));
    }

    void oversizedFrameIsAProtocolError() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsList(this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        QByteArray header(4, Qt::Uninitialized);
        qToBigEndian<quint32>(64 * 1024 + 1, header.data());
        daemon.connection()->write(header);
        daemon.connection()->flush();

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("protocol_error"));
    }

    void foreignRequestIdIsAProtocolError() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsList(this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        daemon.send(
            {{QStringLiteral("type"), QStringLiteral("result")}, {QStringLiteral("result"), QStringLiteral("success")}},
            QStringLiteral("someone-else"));

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("protocol_error"));
    }

    void v1DaemonIsReportedAsOutdated() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsList(this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        daemon.sendRaw(R"({"v":1,"type":"auth_response","request_id":null,"result_code":99})");

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("daemon_outdated"));
    }

    void silentDaemonTimesOut() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsList(this);
        request->setIdleTimeout(200);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("timeout"));
        QVERIFY(daemon.connection()->waitForDisconnected(kWaitMs));
    }

    void framesSplitAcrossReadsAreReassembled() {
        FakeDaemon daemon(m_path);
        auto* request = AuthdRequest::modelsList(this);
        QSignalSpy finished(request, &AuthdRequest::finished);
        request->start();
        daemon.accept();

        const QByteArray body = QJsonDocument(QJsonObject{{QStringLiteral("v"), 2},
                                                          {QStringLiteral("type"), QStringLiteral("result")},
                                                          {QStringLiteral("request_id"), request->requestId()},
                                                          {QStringLiteral("result"), QStringLiteral("success")}})
                                    .toJson(QJsonDocument::Compact);
        QByteArray frame(4, Qt::Uninitialized);
        qToBigEndian<quint32>(static_cast<quint32>(body.size()), frame.data());
        frame += body;
        for (const char byte : frame) {
            daemon.connection()->write(&byte, 1);
            daemon.connection()->flush();
            QTest::qWait(1);
        }

        // the last byte may already have been handled inside qWait()
        QTRY_COMPARE_WITH_TIMEOUT(finished.count(), 1, kWaitMs);
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("success"));
    }

private:
    QTemporaryDir m_dir;
    QString m_path;
};

QTEST_GUILESS_MAIN(TestAuthdRequest)
#include "test_authdrequest.moc"
