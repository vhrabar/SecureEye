#include "PreviewImage.hpp"

#include "CameraSession.hpp"

#include <QPainter>

namespace secureEye {

PreviewImage::PreviewImage(QQuickItem* parent) : QQuickPaintedItem(parent) {}

auto PreviewImage::session() const -> CameraSession* {
    return m_session;
}

void PreviewImage::setSession(CameraSession* session) {
    if (m_session == session) {
        return;
    }
    if (m_session != nullptr) {
        m_session->disconnect(this);
    }
    m_session = session;
    if (m_session != nullptr) {
        connect(m_session, &CameraSession::previewChanged, this, [this] {
            updatePaintedRect();
            update();
        });
    }
    updatePaintedRect();
    update();
    emit sessionChanged();
}

void PreviewImage::setMirrored(const bool mirrored) {
    if (m_mirrored != mirrored) {
        m_mirrored = mirrored;
        update();
        emit mirroredChanged();
    }
}

void PreviewImage::paint(QPainter* painter) {
    if (m_session == nullptr || !m_session->hasPreview()) {
        return;
    }
    const QImage& image = m_session->preview();
    painter->setRenderHint(QPainter::SmoothPixmapTransform);
    painter->drawImage(m_paintedRect, m_mirrored ? image.flipped(Qt::Horizontal) : image);
}

auto PreviewImage::fitRect(const QSizeF& image, const QSizeF& bounds) -> QRectF {
    if (image.isEmpty() || bounds.isEmpty()) {
        return {};
    }
    const QSizeF size = image.scaled(bounds, Qt::KeepAspectRatio);
    return {QPointF((bounds.width() - size.width()) / 2, (bounds.height() - size.height()) / 2), size};
}

void PreviewImage::geometryChange(const QRectF& newGeometry, const QRectF& oldGeometry) {
    QQuickPaintedItem::geometryChange(newGeometry, oldGeometry);
    updatePaintedRect();
}

void PreviewImage::updatePaintedRect() {
    const QSizeF image =
        m_session != nullptr && m_session->hasPreview() ? QSizeF(m_session->preview().size()) : QSizeF();
    if (const QRectF rect = fitRect(image, size()); rect != m_paintedRect) {
        m_paintedRect = rect;
        emit paintedRectChanged();
    }
}

} // namespace secureEye
