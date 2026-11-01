#ifndef SECUREEYE_CAMERADEVICE_HPP
#define SECUREEYE_CAMERADEVICE_HPP

#include <QObject>
#include <QQmlEngine>
#include <QString>

class QFileSystemWatcher;
class QTimer;

namespace secureEye {

// Whether the camera at a device path (video.device_path) is there, and what the kernel calls it. Follows hotplug:
// /dev and the path's own directory are watched, so plugging the camera in or out updates the status.
//
// This only looks at the device node. Whether the daemon can open it, or is using it, is only known once a session
// runs.
class CameraDevice : public QObject {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QString path READ path WRITE setPath NOTIFY pathChanged)
    Q_PROPERTY(Status status READ status NOTIFY statusChanged)
    // e.g. "USB2.0 FHD UVC WebCam"; empty when the kernel does not say.
    Q_PROPERTY(QString name READ name NOTIFY statusChanged)

public:
    enum class Status {
        NotSet,  // empty, or the shipped "none"
        Missing, // nothing at the path
        Present,
    };
    Q_ENUM(Status)

    explicit CameraDevice(QObject* parent = nullptr);

    [[nodiscard]] auto path() const -> QString {
        return m_path;
    }
    void setPath(const QString& path);
    [[nodiscard]] auto status() const -> Status {
        return m_status;
    }
    [[nodiscard]] auto name() const -> QString {
        return m_name;
    }

    // Check the path again now.
    Q_INVOKABLE void refresh();

signals:
    void pathChanged();
    void statusChanged();

private:
    void watch();

    QString m_path;
    Status m_status = Status::NotSet;
    QString m_name;
    QFileSystemWatcher* m_watcher;
    // udev adds the /dev/v4l symlinks a moment after the node itself
    QTimer* m_settle;
};

} // namespace secureEye

#endif // SECUREEYE_CAMERADEVICE_HPP
