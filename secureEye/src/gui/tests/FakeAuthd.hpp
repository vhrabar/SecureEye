#ifndef SECUREEYE_TESTS_FAKEAUTHD_HPP
#define SECUREEYE_TESTS_FAKEAUTHD_HPP

#include <QDeadlineTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocalServer>
#include <QLocalSocket>
#include <QTest>
#include <QtEndian>

#include <memory>

namespace secureEye::testing {

inline constexpr int kWaitMs = 3000;

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
        m_buffer.clear();
        return read();
    }

    auto read() -> QJsonObject {
        if (!m_conn) {
            return {};
        }
        while (m_buffer.size() < 4 || m_buffer.size() < 4 + qFromBigEndian<quint32>(m_buffer.constData())) {
            // the client writes from its event loop, so keep it spinning while waiting
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

} // namespace secureEye::testing

#endif // SECUREEYE_TESTS_FAKEAUTHD_HPP
