#include "system/CameraDevice.hpp"

#include <QFile>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

using secureEye::CameraDevice;

class TestCameraDevice : public QObject {
    Q_OBJECT

private slots:
    void notSet() {
        CameraDevice device;
        QCOMPARE(device.status(), CameraDevice::Status::NotSet);
        device.setPath(QStringLiteral("none"));
        QCOMPARE(device.status(), CameraDevice::Status::NotSet);
        device.setPath(QStringLiteral("  "));
        QCOMPARE(device.status(), CameraDevice::Status::NotSet);
    }

    void missingAndPresent() {
        QTemporaryDir dir;
        const QString path = dir.filePath(QStringLiteral("video9"));
        CameraDevice device;
        device.setPath(path);
        QCOMPARE(device.status(), CameraDevice::Status::Missing);

        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.close();
        device.refresh();
        QCOMPARE(device.status(), CameraDevice::Status::Present);
        // not a video4linux node, so the kernel has no name for it
        QVERIFY(device.name().isEmpty());
    }

    void followsHotplug() {
        QTemporaryDir dir;
        const QString path = dir.filePath(QStringLiteral("video9"));
        CameraDevice device;
        device.setPath(path);
        QSignalSpy changed(&device, &CameraDevice::statusChanged);

        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.close();
        QTRY_COMPARE_WITH_TIMEOUT(device.status(), CameraDevice::Status::Present, 3000);

        QVERIFY(QFile::remove(path));
        QTRY_COMPARE_WITH_TIMEOUT(device.status(), CameraDevice::Status::Missing, 3000);
        QCOMPARE(changed.count(), 2);
    }
};

QTEST_GUILESS_MAIN(TestCameraDevice)
#include "test_cameradevice.moc"
