#ifndef SECUREEYE_PREVIEWIMAGE_HPP
#define SECUREEYE_PREVIEWIMAGE_HPP

#include "CameraSession.hpp"

#include <QPointer>
#include <QQmlEngine>
#include <QQuickPaintedItem>
#include <QRectF>
#include <QSizeF>

namespace secureEye {

// Paints a CameraSession's latest preview, scaled to fit and centred (tp to 10/s)
class PreviewImage : public QQuickPaintedItem {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(secureEye::CameraSession* session READ session WRITE setSession NOTIFY sessionChanged)
    // Show the picture like a mirror
    Q_PROPERTY(bool mirrored READ isMirrored WRITE setMirrored NOTIFY mirroredChanged)
    // Where the image is drawn inside the item, so overlays can line up with it. Empty without a preview.
    Q_PROPERTY(QRectF paintedRect READ paintedRect NOTIFY paintedRectChanged)

public:
    explicit PreviewImage(QQuickItem* parent = nullptr);

    [[nodiscard]] auto session() const -> CameraSession*;
    void setSession(CameraSession* session);
    [[nodiscard]] auto isMirrored() const -> bool {
        return m_mirrored;
    }
    void setMirrored(bool mirrored);
    [[nodiscard]] auto paintedRect() const -> QRectF {
        return m_paintedRect;
    }

    void paint(QPainter* painter) override;

    // The largest rectangle with image's aspect ratio that fits in bounds, centred in it.
    [[nodiscard]] static auto fitRect(const QSizeF& image, const QSizeF& bounds) -> QRectF;

signals:
    void sessionChanged();
    void mirroredChanged();
    void paintedRectChanged();

protected:
    void geometryChange(const QRectF& newGeometry, const QRectF& oldGeometry) override;

private:
    void updatePaintedRect();

    QPointer<CameraSession> m_session;
    bool m_mirrored = true;
    QRectF m_paintedRect;
};

} // namespace secureEye

#endif // SECUREEYE_PREVIEWIMAGE_HPP
