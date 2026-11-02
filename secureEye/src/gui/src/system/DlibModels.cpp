#include "DlibModels.hpp"

#include "core/ConfigStore.hpp"
#include "system/GuiBackend.hpp"

#include <QDir>
#include <QFileInfo>

#include <array>

namespace secureEye {

namespace {

// Keep in sync with secureEye/src/dlib_models.py
constexpr std::array kDataFiles{
    "shape_predictor_5_face_landmarks.dat",
    "mmod_human_face_detector.dat",
    "dlib_face_recognition_resnet_model_v1.dat",
};

} // namespace

DlibModels::DlibModels(QObject* parent) : QObject(parent) {
    connect(ConfigStore::instance(), &ConfigStore::valueChanged, this,
            [this](const QString& section, const QString& key) {
                if (section == QLatin1String("core") && key == QLatin1String("detector_backend")) {
                    emit requiredChanged();
                    emit canFetchChanged();
                    refresh();
                }
            });
    refresh();
}

auto DlibModels::instance() -> DlibModels* {
    static DlibModels models;
    return &models;
}

auto DlibModels::create(QQmlEngine* /*engine*/, QJSEngine* /*scriptEngine*/) -> DlibModels* {
    DlibModels* const models = instance();
    QJSEngine::setObjectOwnership(models, QJSEngine::CppOwnership);

    return models;
}

auto DlibModels::directory() -> QString {
    // Same override as paths_factory.py, so the dev sandbox looks where the daemon looks.
    const QString overridden = qEnvironmentVariable("SECUREEYE_DLIB_DATA_DIR");
    return overridden.isEmpty() ? QStringLiteral(SECUREEYE_DLIB_DATA_DIR) : overridden;
}

auto DlibModels::isRequired() const -> bool {
    const QString backend =
        ConfigStore::instance()->value(QStringLiteral("core"), QStringLiteral("detector_backend")).toString();
    return backend.trimmed().compare(QLatin1String("dlib"), Qt::CaseInsensitive) == 0;
}

void DlibModels::refresh() {
    const QDir dir(directory());
    bool present = true;
    for (const char* name : kDataFiles) {
        if (!QFileInfo(dir.filePath(QString::fromLatin1(name))).isFile()) {
            present = false;
            break;
        }
    }

    if (present != m_present) {
        m_present = present;
        emit presentChanged();
        emit canFetchChanged();
    }
}

void DlibModels::setBackend(GuiBackend* backend) {
    if (m_backend != nullptr) {
        disconnect(m_backend, nullptr, this, nullptr);
    }
    m_backend = backend;
    if (m_backend == nullptr) {
        return;
    }

    connect(m_backend, &GuiBackend::finished, this, [this](const int id, const QJsonValue& /*data*/) {
        if (id == m_job) {
            finish();
            emit fetched();
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

void DlibModels::fetch() {
    if (!canFetch()) {
        return;
    }
    if (m_backend == nullptr) {
        emit failed(tr("The dlib data files can not be downloaded from here."));
        return;
    }

    m_job = m_backend->run(QStringLiteral("fetch-models"), {}, GuiBackend::Privilege::Admin);
    emit busyChanged();
    emit canFetchChanged();
}

void DlibModels::finish() {
    m_job = 0;
    emit busyChanged();
    refresh();
    emit canFetchChanged();
}

} // namespace secureEye
