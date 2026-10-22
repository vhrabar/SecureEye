#include "AuthdRequest.hpp"

#include <QJsonDocument>
#include <QJsonValue>
#include <QTimer>
#include <QUuid>
#include <QtEndian>

#include <pwd.h>
#include <unistd.h>

namespace secureEye {

namespace {

constexpr int kVersion = 2;

// The daemon caps its own frames at 64 KiB (MAX_EVENT_PAYLOAD); anything bigger is not from authd.
constexpr quint32 kMaxFrame = 64 * 1024;
constexpr int kHeaderSize = 4;

// Covers the daemon's 5 s wait for a busy camera plus loading the pipeline. Camera sessions send a frame event per
// camera frame, so a session that goes quiet this long is stuck.
constexpr int kDefaultIdleTimeoutMs = 15000;

auto key(const char* name) -> QString {
    return QString::fromLatin1(name);
}

} // namespace

auto AuthdRequest::modelsList(QObject* parent) -> AuthdRequest* {
    return new AuthdRequest(key("models_list"), {}, parent);
}

auto AuthdRequest::modelsRemove(const int model, QObject* parent) -> AuthdRequest* {
    return new AuthdRequest(key("models_remove"), {{key("model"), model}}, parent);
}

auto AuthdRequest::modelsClear(QObject* parent) -> AuthdRequest* {
    return new AuthdRequest(key("models_clear"), {}, parent);
}

auto AuthdRequest::enroll(const QString& label, const bool replace, const bool preview, QObject* parent)
    -> AuthdRequest* {
    return new AuthdRequest(key("enroll"),
                            {{key("label"), label}, {key("replace"), replace}, {key("preview"), preview}}, parent);
}

auto AuthdRequest::test(const int durationMs, const bool preview, QObject* parent) -> AuthdRequest* {
    return new AuthdRequest(key("test"), {{key("duration_ms"), durationMs}, {key("preview"), preview}}, parent);
}

AuthdRequest::AuthdRequest(const QString& type, const QJsonObject& fields, QObject* parent)
    : QObject(parent), m_request(fields), m_socket(new QLocalSocket(this)), m_idleTimer(new QTimer(this)) {
    m_request.insert(key("v"), kVersion);
    m_request.insert(key("type"), type);
    m_request.insert(key("request_id"), QUuid::createUuid().toString(QUuid::Id128));
    m_request.insert(key("username"), currentUser());

    m_idleTimer->setSingleShot(true);
    m_idleTimer->setInterval(kDefaultIdleTimeoutMs);
    connect(m_idleTimer, &QTimer::timeout, this, [this] { finish(key("timeout")); });

    connect(m_socket, &QLocalSocket::connected, this, &AuthdRequest::onConnected);
    connect(m_socket, &QLocalSocket::readyRead, this, &AuthdRequest::onReadyRead);
    connect(m_socket, &QLocalSocket::disconnected, this, &AuthdRequest::onDisconnected);
    connect(m_socket, &QLocalSocket::errorOccurred, this, &AuthdRequest::onSocketError);
}

AuthdRequest::~AuthdRequest() {
    // Closing the connection is the cancel; nobody is left to hear about it.
    m_socket->disconnect(this);
    m_socket->abort();
}

auto AuthdRequest::type() const -> QString {
    return m_request.value(key("type")).toString();
}

auto AuthdRequest::requestId() const -> QString {
    return m_request.value(key("request_id")).toString();
}

auto AuthdRequest::idleTimeout() const -> int {
    return m_idleTimer->interval();
}

void AuthdRequest::setIdleTimeout(const int ms) {
    m_idleTimer->setInterval(ms);
}

auto AuthdRequest::socketPath() -> QString {
    // Same variable the daemon reads, so a test or development daemon can be reached on another path.
    const QString overridden = qEnvironmentVariable("SECUREEYE_AUTHD_SOCKET");
    return overridden.isEmpty() ? QStringLiteral(AUTHD_SOCKET_PATH) : overridden;
}

auto AuthdRequest::currentUser() -> QString {
    const passwd* entry = getpwuid(getuid());
    return entry != nullptr ? QString::fromLocal8Bit(entry->pw_name) : QString();
}

void AuthdRequest::start() {
    if (m_state != State::Idle) {
        return;
    }
    m_state = State::Connecting;
    m_idleTimer->start();
    // QLocalSocket may report a missing socket from inside connectToServer(); deferring keeps every signal after
    // start() has returned, so callers never see finished() before they are back in the event loop.
    QTimer::singleShot(0, this, [this] {
        if (m_state == State::Connecting) {
            m_socket->connectToServer(socketPath());
        }
    });
}

void AuthdRequest::cancel() {
    switch (m_state) {
    case State::Running:
        // The daemon stops the session and still sends its result, with the frame counts so far.
        send({{key("v"), kVersion}, {key("type"), key("cancel")}, {key("request_id"), requestId()}});
        break;
    case State::Idle:
    case State::Connecting:
    case State::Waiting:
        finish(key("cancelled"));
        break;
    case State::Finished:
        break;
    }
}

void AuthdRequest::onConnected() {
    m_state = State::Waiting;
    send(m_request);
}

void AuthdRequest::onReadyRead() {
    m_buffer += m_socket->readAll();
    while (m_state != State::Finished && m_buffer.size() >= kHeaderSize) {
        const auto length = qFromBigEndian<quint32>(m_buffer.constData());
        if (length < 1 || length > kMaxFrame) {
            finish(key("protocol_error"));
            return;
        }
        if (m_buffer.size() < kHeaderSize + static_cast<qsizetype>(length)) {
            return;
        }
        const QByteArray body = m_buffer.mid(kHeaderSize, length);
        m_buffer.remove(0, kHeaderSize + static_cast<qsizetype>(length));

        QJsonParseError error{};
        const QJsonDocument document = QJsonDocument::fromJson(body, &error);
        if (error.error != QJsonParseError::NoError || !document.isObject()) {
            finish(key("protocol_error"));
            return;
        }
        handleMessage(document.object());
    }
}

void AuthdRequest::handleMessage(const QJsonObject& message) {
    const QString messageType = message.value(key("type")).toString();
    if (messageType == key("auth_response")) {
        // a daemon from before protocol v2 answers everything as a failed v1 login
        finish(key("daemon_outdated"));
        return;
    }
    const QJsonValue id = message.value(key("request_id"));
    // invalid_request answers carry a null id when the id itself was the problem
    const bool idMatches = id.toString() == requestId() || (messageType == key("result") && id.isNull());
    if (message.value(key("v")).toInt() != kVersion || !idMatches) {
        finish(key("protocol_error"));
        return;
    }

    m_idleTimer->start();
    if (messageType == key("started")) {
        m_state = State::Running;
        emit started();
    } else if (messageType == key("frame")) {
        QImage preview;
        const QJsonValue encoded = message.value(key("preview"));
        if (encoded.isString()) {
            preview = QImage::fromData(QByteArray::fromBase64(encoded.toString().toLatin1()), "JPEG");
        }
        emit frameReceived(message.value(key("report")).toObject(), preview);
    } else if (messageType == key("result")) {
        finish(message.value(key("result")).toString(), message.value(key("data")).toObject());
    }
    // unknown event types are left for newer clients
}

void AuthdRequest::onDisconnected() {
    finish(key("connection_lost"));
}

void AuthdRequest::onSocketError(const QLocalSocket::LocalSocketError error) {
    if (m_state == State::Connecting) {
        finish(key("daemon_unavailable"));
        return;
    }
    // A closed peer also arrives as disconnected(); anything else ends the request too.
    if (error != QLocalSocket::PeerClosedError) {
        finish(key("connection_lost"));
    }
}

void AuthdRequest::finish(const QString& result, const QJsonObject& data) {
    if (m_state == State::Finished) {
        return;
    }
    m_state = State::Finished;
    m_idleTimer->stop();
    m_socket->disconnect(this);
    m_socket->abort();
    emit finished(result, data);
}

void AuthdRequest::send(const QJsonObject& message) {
    const QByteArray body = QJsonDocument(message).toJson(QJsonDocument::Compact);
    QByteArray frame(kHeaderSize, Qt::Uninitialized);
    qToBigEndian<quint32>(static_cast<quint32>(body.size()), frame.data());
    frame += body;
    m_socket->write(frame);
}

} // namespace secureEye
