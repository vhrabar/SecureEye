#include "CameraDevice.hpp"

#include <QFile>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QTimer>

namespace secureEye {

namespace {

constexpr int kSettleMs = 300;

// The name V4L2 gives the device, e.g. "USB2.0 FHD UVC WebCam: USB2.0 F".
auto kernelName(const QString& path) -> QString {
    const QString node = QFileInfo(QFileInfo(path).canonicalFilePath()).fileName();
    if (node.isEmpty()) {
        return {};
    }
    QFile file(QStringLiteral("/sys/class/video4linux/%1/name").arg(node));
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    QString name = QString::fromUtf8(file.readAll()).trimmed();
    // UVC appends ": <interface>" to the model; the model alone is what people recognise
    if (const qsizetype colon = name.indexOf(QStringLiteral(": ")); colon > 0) {
        name.truncate(colon);
    }
    return name;
}

} // namespace

CameraDevice::CameraDevice(QObject* parent)
    : QObject(parent), m_watcher(new QFileSystemWatcher(this)), m_settle(new QTimer(this)) {
    m_settle->setSingleShot(true);
    m_settle->setInterval(kSettleMs);
    connect(m_settle, &QTimer::timeout, this, &CameraDevice::refresh);
    connect(m_watcher, &QFileSystemWatcher::directoryChanged, m_settle, qOverload<>(&QTimer::start));
}

void CameraDevice::setPath(const QString& path) {
    if (m_path == path) {
        return;
    }
    m_path = path;
    emit pathChanged();
    watch();
    refresh();
}

void CameraDevice::refresh() {
    const QString path = m_path.trimmed();
    Status status = Status::Present;
    QString name;
    if (path.isEmpty() || path == QStringLiteral("none")) {
        status = Status::NotSet;
    } else if (!QFileInfo::exists(path)) {
        status = Status::Missing;
    } else {
        name = kernelName(path);
    }
    if (status != m_status || name != m_name) {
        m_status = status;
        m_name = name;
        emit statusChanged();
    }
}

void CameraDevice::watch() {
    if (const QStringList watched = m_watcher->directories(); !watched.isEmpty()) {
        m_watcher->removePaths(watched);
    }
    QStringList directories{QStringLiteral("/dev")};
    // e.g. /dev/v4l/by-id for a stable symlink; it may not exist until the camera is plugged in
    const QString parent = QFileInfo(m_path).absolutePath();
    if (!m_path.isEmpty() && parent != QStringLiteral("/dev") && QFileInfo(parent).isDir()) {
        directories << parent;
    }
    m_watcher->addPaths(directories);
}

} // namespace secureEye
