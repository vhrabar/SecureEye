#include "GuiBackend.hpp"

#include <QFileInfo>
#include <QStandardPaths>
#include <QTimer>

namespace secureEye {

namespace {

// pkexec(1):
// 126 when the authentication dialog was dismissed
// 127 when authorization failed or could not be obtained.
constexpr int kPkexecDismissed = 126;
constexpr int kPkexecNotAuthorized = 127;

constexpr int kTerminateGraceMs = 2000;

auto commandOutputMessage(QProcess* process, const int exitCode) -> QString {
    QString message = QString::fromUtf8(process->readAllStandardError()).trimmed();
    if (message.isEmpty()) {
        message = QString::fromUtf8(process->readAllStandardOutput()).trimmed();
    }
    if (message.isEmpty()) {
        message = GuiBackend::tr("secureEye exited with code %1.").arg(exitCode);
    }
    return message;
}

} // namespace

GuiBackend::GuiBackend(QObject* parent) : QObject(parent) {}

GuiBackend::~GuiBackend() {
    // Unprivileged calls can still be stopped; privileged ones are already out of our hands.
    for (QProcess* process : std::as_const(m_jobs)) {
        process->disconnect(this);
        process->kill();
    }
}

auto GuiBackend::cliPath() -> QString {
    const QString overridden = qEnvironmentVariable("SECUREEYE_CLI_PATH");
    return overridden.isEmpty() ? QStringLiteral(SECUREEYE_CLI_PATH) : overridden;
}

auto GuiBackend::run(const QString& command, const QStringList& args, Privilege privilege) -> int {
    const int id = m_nextId++;

    const auto failLater = [this, id](Error error, const QString& message) {
        // Emitted from the event loop so the caller has the id before any signal for it arrives.
        QTimer::singleShot(0, this, [this, id, error, message] { emit failed(id, error, message); });
    };

    const QString cli = cliPath();
    if (!QFileInfo(cli).isExecutable()) {
        failLater(Error::NotStarted, tr("The secureEye command was not found at %1.").arg(cli));
        return id;
    }

    // The command must stay first: pkexec matches it against the exec.argv1 annotation to pick the polkit action.
    QStringList arguments{command};
    arguments += args;
    arguments += QStringLiteral("--plain");

    QString program = cli;
    if (privilege == Privilege::Admin) {
        // pkexec needs an absolute path to match the polkit action
        program = QStandardPaths::findExecutable(QStringLiteral("pkexec"));
        if (program.isEmpty()) {
            failLater(Error::NotStarted, tr("pkexec was not found. Install polkit to make changes that need "
                                            "administrator privileges."));
            return id;
        }
        arguments.prepend(cli);
    }

    auto* process = new QProcess(this);
    process->setProgram(program);
    process->setArguments(arguments);
    process->setProcessChannelMode(QProcess::SeparateChannels);

    connect(process, &QProcess::finished, this, [this, id](const int exitCode, const QProcess::ExitStatus status) {
        onProcessFinished(id, exitCode, status);
    });
    connect(process, &QProcess::errorOccurred, this,
            [this, id](const QProcess::ProcessError error) { onProcessError(id, error); });

    const bool wasBusy = isBusy();
    m_jobs.insert(id, process);
    m_privileges.insert(id, privilege);
    if (!wasBusy) {
        emit busyChanged();
    }

    process->start();
    return id;
}

void GuiBackend::cancel(int id) {
    m_privileges.remove(id);
    QProcess* process = take(id);
    if (process == nullptr) {
        return;
    }

    process->disconnect(this);
    connect(process, &QProcess::finished, process, &QObject::deleteLater);
    process->terminate();
    QTimer::singleShot(kTerminateGraceMs, process, [process] { process->kill(); });

    emit cancelled(id);
}

auto GuiBackend::take(const int id) -> QProcess* {
    QProcess* process = m_jobs.take(id);
    if (process != nullptr && m_jobs.isEmpty()) {
        emit busyChanged();
    }
    return process;
}

void GuiBackend::onProcessFinished(const int id, const int exitCode, const QProcess::ExitStatus status) {
    const Privilege privilege = m_privileges.take(id);
    QProcess* process = take(id);
    if (process == nullptr) {
        return;
    }
    process->deleteLater();

    if (status == QProcess::CrashExit) {
        emit failed(id, Error::Crashed, tr("secureEye stopped unexpectedly."));
        return;
    }

    if (privilege == Privilege::Admin && exitCode == kPkexecDismissed) {
        emit failed(id, Error::AuthDismissed, tr("Authentication was cancelled."));
        return;
    }
    if (privilege == Privilege::Admin && exitCode == kPkexecNotAuthorized) {
        emit failed(id, Error::NotAuthorized, tr("You are not authorized to perform this action."));
        return;
    }

    if (exitCode != 0) {
        emit failed(id, Error::CommandFailed, commandOutputMessage(process, exitCode));
        return;
    }

    emit finished(id, process->readAllStandardOutput());
}

void GuiBackend::onProcessError(const int id, const QProcess::ProcessError error) {
    // Crashes also arrive through finished(), which reports them. Only a failed start never reaches it.
    if (error != QProcess::FailedToStart) {
        return;
    }

    m_privileges.remove(id);
    QProcess* process = take(id);
    if (process == nullptr) {
        return;
    }
    process->deleteLater();

    emit failed(id, Error::NotStarted, process->errorString());
}

} // namespace secureEye
