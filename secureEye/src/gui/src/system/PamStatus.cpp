#include "PamStatus.hpp"

#include "core/ConfigStore.hpp"
#include "system/GuiBackend.hpp"

namespace secureEye {

PamStatus::PamStatus(QObject* parent) : QObject(parent) {
    connect(ConfigStore::instance(), &ConfigStore::valueChanged, this,
            [this](const QString& section, const QString& key) {
                if (section == QLatin1String("core") && key == QLatin1String("disabled")) {
                    emit enabledChanged();
                }
            });
}

auto PamStatus::instance() -> PamStatus* {
    static PamStatus status;
    return &status;
}

auto PamStatus::create(QQmlEngine* /*engine*/, QJSEngine* /*scriptEngine*/) -> PamStatus* {
    PamStatus* const status = instance();
    QJSEngine::setObjectOwnership(status, QJSEngine::CppOwnership);

    return status;
}

auto PamStatus::isEnabled() const -> bool {
    return !ConfigStore::instance()->value(QStringLiteral("core"), QStringLiteral("disabled")).toBool();
}

void PamStatus::setBackend(GuiBackend* backend) {
    if (m_backend != nullptr) {
        disconnect(m_backend, nullptr, this, nullptr);
    }
    m_backend = backend;
    if (m_backend == nullptr) {
        return;
    }

    connect(m_backend, &GuiBackend::finished, this, [this](const int id) {
        if (id == m_job) {
            finish();
        }
    });
    connect(m_backend, &GuiBackend::failed, this,
            [this](const int id, GuiBackend::Error /*error*/, const QString& /*code*/, const QString& message) {
                if (id == m_job) {
                    finish();
                    emit failed(message);
                }
            });
}

void PamStatus::setEnabled(const bool enabled) {
    if (isBusy() || enabled == isEnabled()) {
        return;
    }
    if (m_backend == nullptr) {
        emit failed(tr("Face authentication can not be switched from here."));
        return;
    }

    // `disable 1` turns face authentication off, `disable 0` turns it back on.
    m_job = m_backend->run(QStringLiteral("disable"), {enabled ? QStringLiteral("0") : QStringLiteral("1")},
                           GuiBackend::Privilege::Admin);
    emit busyChanged();
}

void PamStatus::finish() {
    m_job = 0;
    emit busyChanged();
    emit enabledChanged();
}

} // namespace secureEye
