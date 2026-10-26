#include "FakeAuthd.hpp"
#include "system/CameraSession.hpp"
#include "system/PreviewImage.hpp"

#include <QBuffer>
#include <QJsonArray>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

#include <cmath>

using secureEye::CameraSession;
using secureEye::PreviewImage;
using secureEye::testing::FakeDaemon;
using secureEye::testing::kWaitMs;

namespace {

auto jpegBase64(const QSize& size) -> QString {
    QImage image(size, QImage::Format_RGB888);
    image.fill(Qt::gray);
    QByteArray bytes;
    QBuffer buffer(&bytes);
    buffer.open(QIODevice::WriteOnly);
    image.save(&buffer, "JPEG");
    return QString::fromLatin1(bytes.toBase64());
}

auto daemonEvent(const QString& type) -> QJsonObject {
    return {{QStringLiteral("type"), type}};
}

auto frame(const QJsonObject& report, const QString& preview = {}) -> QJsonObject {
    QJsonObject message{{QStringLiteral("type"), QStringLiteral("frame")}, {QStringLiteral("report"), report}};
    if (!preview.isEmpty()) {
        message.insert(QStringLiteral("preview"), preview);
    }
    return message;
}

auto result(const QString& result, const QJsonObject& data = {}) -> QJsonObject {
    return {{QStringLiteral("type"), QStringLiteral("result")},
            {QStringLiteral("result"), result},
            {QStringLiteral("data"), data}};
}

} // namespace

class TestCameraSession : public QObject {
    Q_OBJECT

private slots:
    void init() {
        QVERIFY(m_dir.isValid());
        m_path = m_dir.filePath(QStringLiteral("authd.sock"));
        qputenv("SECUREEYE_AUTHD_SOCKET", m_path.toLocal8Bit());
    }

    void enrollFromStartToResult() {
        FakeDaemon daemon(m_path);
        CameraSession session;
        session.setLabel(QStringLiteral("desk"));
        session.setReplace(true);
        QSignalSpy finished(&session, &CameraSession::finished);

        session.start();
        QCOMPARE(session.state(), CameraSession::State::Waiting);
        QVERIFY(session.isActive());

        const QJsonObject request = daemon.accept();
        QCOMPARE(request.value(QStringLiteral("type")).toString(), QStringLiteral("enroll"));
        QCOMPARE(request.value(QStringLiteral("label")).toString(), QStringLiteral("desk"));
        QVERIFY(request.value(QStringLiteral("replace")).toBool());
        QVERIFY(request.value(QStringLiteral("preview")).toBool());
        const QString id = request.value(QStringLiteral("request_id")).toString();

        daemon.send(daemonEvent(QStringLiteral("started")), id);
        QTRY_COMPARE_WITH_TIMEOUT(session.state(), CameraSession::State::Running, kWaitMs);

        daemon.send(frame({{QStringLiteral("state"), QStringLiteral("face")},
                           {QStringLiteral("darkness"), 12.5},
                           {QStringLiteral("dark_threshold"), 60},
                           {QStringLiteral("faces"), QJsonArray{QJsonArray{0.25, 0.5, 0.25, 0.4}}},
                           {QStringLiteral("distance"), QJsonValue::Null},
                           {QStringLiteral("certainty"), QJsonValue::Null}},
                          jpegBase64(QSize(320, 240))),
                    id);
        QTRY_COMPARE_WITH_TIMEOUT(session.frameCount(), 1, kWaitMs);
        QCOMPARE(session.frameState(), QStringLiteral("face"));
        QCOMPARE(session.faces().size(), 1);
        QCOMPARE(session.faces().at(0).toRectF(), QRectF(0.25, 0.5, 0.25, 0.4));
        QVERIFY(std::isnan(session.distance()));
        QCOMPARE(session.darkness(), 12.5);
        QCOMPARE(session.darkThreshold(), 60.0);
        QVERIFY(session.hasPreview());
        QCOMPARE(session.preview().size(), QSize(320, 240));

        daemon.send(result(QStringLiteral("success"), {{QStringLiteral("model"), 4}}), id);
        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(finished.at(0).at(0).toString(), QStringLiteral("success"));
        QCOMPARE(session.state(), CameraSession::State::Finished);
        QVERIFY(!session.isActive());
        QCOMPARE(session.resultData().value(QStringLiteral("model")).toInt(), 4);
        QVERIFY(!session.resultMessage().isEmpty());
        // the last picture stays up after the session, so the result has something to sit next to
        QVERIFY(session.hasPreview());
    }

    void testReportsDistances() {
        FakeDaemon daemon(m_path);
        CameraSession session;
        session.setMode(CameraSession::Mode::Test);
        session.setDurationMs(5000);
        session.start();

        const QJsonObject request = daemon.accept();
        QCOMPARE(request.value(QStringLiteral("type")).toString(), QStringLiteral("test"));
        QCOMPARE(request.value(QStringLiteral("duration_ms")).toInt(), 5000);
        const QString id = request.value(QStringLiteral("request_id")).toString();

        daemon.send(daemonEvent(QStringLiteral("started")), id);
        daemon.send(frame({{QStringLiteral("state"), QStringLiteral("match")},
                           {QStringLiteral("distance"), 2.4},
                           {QStringLiteral("certainty"), 3.5}}),
                    id);
        QTRY_COMPARE_WITH_TIMEOUT(session.frameCount(), 1, kWaitMs);
        QCOMPARE(session.distance(), 2.4);
        QCOMPARE(session.certainty(), 3.5);
        // frames without a preview keep whatever was shown before
        QVERIFY(!session.hasPreview());
    }

    void cancelAsksTheDaemon() {
        FakeDaemon daemon(m_path);
        CameraSession session;
        session.setMode(CameraSession::Mode::Test);
        session.start();
        const QString id = daemon.accept().value(QStringLiteral("request_id")).toString();
        daemon.send(daemonEvent(QStringLiteral("started")), id);
        QTRY_COMPARE_WITH_TIMEOUT(session.state(), CameraSession::State::Running, kWaitMs);

        session.cancel();

        QCOMPARE(daemon.read().value(QStringLiteral("type")).toString(), QStringLiteral("cancel"));
        daemon.send(result(QStringLiteral("cancelled")), id);
        QTRY_COMPARE_WITH_TIMEOUT(session.result(), QStringLiteral("cancelled"), kWaitMs);
    }

    void destroyingTheSessionReleasesTheCamera() {
        FakeDaemon daemon(m_path);
        auto* session = new CameraSession;
        session->setMode(CameraSession::Mode::Test);
        session->start();
        daemon.accept();

        delete session;

        QVERIFY(daemon.connection()->waitForDisconnected(kWaitMs));
    }

    void stoppedDaemon() {
        CameraSession session;
        QSignalSpy finished(&session, &CameraSession::finished);
        session.start();

        QVERIFY(finished.wait(kWaitMs));
        QCOMPARE(session.result(), QStringLiteral("daemon_unavailable"));
        QVERIFY(!session.resultMessage().isEmpty());
    }

    void restartClearsTheLastSession() {
        FakeDaemon daemon(m_path);
        CameraSession session;
        session.start();
        const QString id = daemon.accept().value(QStringLiteral("request_id")).toString();
        daemon.send(daemonEvent(QStringLiteral("started")), id);
        daemon.send(frame({{QStringLiteral("state"), QStringLiteral("no_face")}}, jpegBase64(QSize(32, 24))), id);
        daemon.send(result(QStringLiteral("no_face")), id);
        QTRY_COMPARE_WITH_TIMEOUT(session.state(), CameraSession::State::Finished, kWaitMs);
        QVERIFY(session.hasPreview());

        session.start();

        QCOMPARE(session.state(), CameraSession::State::Waiting);
        QVERIFY(!session.hasPreview());
        QCOMPARE(session.frameCount(), 0);
        QVERIFY(session.frameState().isEmpty());
        QVERIFY(session.result().isEmpty());
        QCOMPARE(daemon.accept().value(QStringLiteral("type")).toString(), QStringLiteral("enroll"));
    }

    void resetDropsARunningSession() {
        FakeDaemon daemon(m_path);
        CameraSession session;
        QSignalSpy finished(&session, &CameraSession::finished);
        session.start();
        const QString id = daemon.accept().value(QStringLiteral("request_id")).toString();
        daemon.send(daemonEvent(QStringLiteral("started")), id);
        daemon.send(frame({{QStringLiteral("state"), QStringLiteral("face")}}, jpegBase64(QSize(32, 24))), id);
        QTRY_VERIFY_WITH_TIMEOUT(session.hasPreview(), kWaitMs);

        session.reset();

        QCOMPARE(session.state(), CameraSession::State::Idle);
        QVERIFY(!session.hasPreview());
        QCOMPARE(session.frameCount(), 0);
        // closing the connection is the cancel; the dropped session reports nothing
        QVERIFY(daemon.connection()->waitForDisconnected(kWaitMs));
        QTest::qWait(100);
        QCOMPARE(finished.count(), 0);
    }

    void startWhileActiveIsIgnored() {
        FakeDaemon daemon(m_path);
        CameraSession session;
        session.start();
        daemon.accept();

        session.start();

        QTest::qWait(100);
        QVERIFY(daemon.connection()->state() == QLocalSocket::ConnectedState);
    }

    void fitRectCentresTheImage() {
        QCOMPARE(PreviewImage::fitRect(QSizeF(320, 240), QSizeF(400, 400)), QRectF(0, 50, 400, 300));
        QCOMPARE(PreviewImage::fitRect(QSizeF(320, 240), QSizeF(800, 300)), QRectF(200, 0, 400, 300));
        QVERIFY(PreviewImage::fitRect(QSizeF(), QSizeF(400, 400)).isEmpty());
    }

private:
    QTemporaryDir m_dir;
    QString m_path;
};

QTEST_MAIN(TestCameraSession)
#include "test_camerasession.moc"
