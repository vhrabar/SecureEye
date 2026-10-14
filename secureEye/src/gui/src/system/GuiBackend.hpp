#ifndef SECUREEYE_GUIBACKEND_HPP
#define SECUREEYE_GUIBACKEND_HPP

#include <QByteArray>
#include <QHash>
#include <QObject>
#include <QProcess>
#include <QString>
#include <QStringList>

namespace secureEye {

// The single place the GUI runs the secureEye CLI.
// Privileged commands go through pkexec, so the polkit prompt and the root boundary stay outside the GUI process.
class GuiBackend : public QObject {
    Q_OBJECT

    Q_PROPERTY(bool busy READ isBusy NOTIFY busyChanged)

public:
    enum class Privilege {
        User,  // run as the GUI user
        Admin, // run as root through pkexec
    };
    Q_ENUM(Privilege)

    enum class Error {
        NotStarted,    // pkexec or the CLI could not be executed
        Crashed,       // the process died from a signal
        AuthDismissed, // the user closed the polkit dialog (pkexec exit 126)
        NotAuthorized, // polkit refused the action (pkexec exit 127)
        CommandFailed, // the CLI ran and exited non-zero
    };
    Q_ENUM(Error)

    explicit GuiBackend(QObject* parent = nullptr);
    ~GuiBackend() override;

    auto run(const QString& command, const QStringList& args = {}, Privilege privilege = Privilege::User) -> int;

    void cancel(int id);

    [[nodiscard]] auto isBusy() const -> bool {
        return !m_jobs.isEmpty();
    }
    [[nodiscard]] static auto cliPath() -> QString;

signals:
    void finished(int id, const QByteArray& output);
    void failed(int id, secureEye::GuiBackend::Error error, const QString& message);
    void cancelled(int id);
    void busyChanged();

private:
    void onProcessFinished(int id, int exitCode, QProcess::ExitStatus status);
    void onProcessError(int id, QProcess::ProcessError error);
    auto take(int id) -> QProcess*;

    QHash<int, QProcess*> m_jobs;
    QHash<int, Privilege> m_privileges;
    int m_nextId = 1;
};

} // namespace secureEye

#endif // SECUREEYE_GUIBACKEND_HPP
