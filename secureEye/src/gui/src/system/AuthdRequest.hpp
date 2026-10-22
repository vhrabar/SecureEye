#ifndef SECUREEYE_AUTHDREQUEST_HPP
#define SECUREEYE_AUTHDREQUEST_HPP

#include <QByteArray>
#include <QImage>
#include <QJsonObject>
#include <QLocalSocket>
#include <QObject>
#include <QString>

class QTimer;

namespace secureEye {

// One management request to secureeye-authd over protocol v2
//
// Each request has its own connection. Connect to the signals, then call start(); finished() is emitted exactly once.
// Destroying the request closes the connection, which the daemon treats as a cancel, so a closed dialog or a quitting
// app can never leave the camera on.
//
// finished() reports these from the client side:
//   "daemon_unavailable"  the socket could not be reached (daemon stopped or not installed)
//   "connection_lost"     the daemon closed the connection before sending a result
//   "daemon_outdated"     the daemon only speaks protocol v1
//   "protocol_error"      the daemon sent something this client does not understand
//   "timeout"             the daemon sent nothing for idleTimeout() milliseconds
//   "cancelled"           cancel() before the session had started
class AuthdRequest : public QObject {
    Q_OBJECT

public:
    enum class State {
        Idle,       // not started
        Connecting, // waiting for the socket
        Waiting,    // request sent, waiting for the camera or the answer
        Running,    // camera session started, frames arriving
        Finished,   // finished() has been emitted
    };
    Q_ENUM(State)

    // Requests for the user running the GUI; the daemon refuses other users for non-root clients.
    static auto modelsList(QObject* parent = nullptr) -> AuthdRequest*;
    static auto modelsRemove(int model, QObject* parent = nullptr) -> AuthdRequest*;
    static auto modelsClear(QObject* parent = nullptr) -> AuthdRequest*;
    static auto enroll(const QString& label, bool replace, bool preview, QObject* parent = nullptr) -> AuthdRequest*;
    static auto test(int durationMs, bool preview, QObject* parent = nullptr) -> AuthdRequest*;

    // type is the v2 request type; fields are added to the request next to v, type, request_id and username.
    AuthdRequest(const QString& type, const QJsonObject& fields, QObject* parent = nullptr);
    ~AuthdRequest() override;

    void start();
    // Ask a running camera session to stop; the daemon then finishes it with "cancelled" (or "success" if it was
    // already saving). Anything not yet running is dropped and finishes with "cancelled" right away.
    void cancel();

    [[nodiscard]] auto state() const -> State {
        return m_state;
    }
    [[nodiscard]] auto type() const -> QString;
    [[nodiscard]] auto requestId() const -> QString;

    [[nodiscard]] auto idleTimeout() const -> int;
    void setIdleTimeout(int ms);

    [[nodiscard]] static auto socketPath() -> QString;
    [[nodiscard]] static auto currentUser() -> QString;

signals:
    // The daemon got the camera for an enroll or test session.
    void started();
    // report is the daemon's per-frame report; preview is null when the frame carried none.
    void frameReceived(const QJsonObject& report, const QImage& preview);
    void finished(const QString& result, const QJsonObject& data);

private:
    void onConnected();
    void onReadyRead();
    void onDisconnected();
    void onSocketError(QLocalSocket::LocalSocketError error);
    void handleMessage(const QJsonObject& message);
    void finish(const QString& result, const QJsonObject& data = {});
    void send(const QJsonObject& message);

    QJsonObject m_request;
    QLocalSocket* m_socket;
    QTimer* m_idleTimer;
    QByteArray m_buffer;
    State m_state = State::Idle;
};

} // namespace secureEye

#endif // SECUREEYE_AUTHDREQUEST_HPP
