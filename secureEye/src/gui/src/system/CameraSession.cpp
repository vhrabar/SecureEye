#include "CameraSession.hpp"

#include "AuthdRequest.hpp"
#include "ModelStore.hpp"

#include <QJsonArray>

#include <limits>

namespace secureEye {

namespace {

constexpr qreal kNoValue = std::numeric_limits<qreal>::quiet_NaN();

// JSON null and missing both mean "not measured"
auto numberOr(const QJsonValue& value, const qreal fallback) -> qreal {
    return value.isDouble() ? value.toDouble() : fallback;
}

} // namespace

CameraSession::CameraSession(QObject* parent) : QObject(parent), m_distance(kNoValue), m_certainty(kNoValue) {}

// m_request is a child; deleting it closes the connection, which the daemon takes as a cancel.
CameraSession::~CameraSession() = default;

void CameraSession::setMode(const Mode mode) {
    if (m_mode != mode) {
        m_mode = mode;
        emit modeChanged();
    }
}

void CameraSession::setLabel(const QString& label) {
    if (m_label != label) {
        m_label = label;
        emit labelChanged();
    }
}

void CameraSession::setReplace(const bool replace) {
    if (m_replace != replace) {
        m_replace = replace;
        emit replaceChanged();
    }
}

void CameraSession::setDurationMs(const int durationMs) {
    if (m_durationMs != durationMs) {
        m_durationMs = durationMs;
        emit durationMsChanged();
    }
}

auto CameraSession::resultMessage() const -> QString {
    return m_result.isEmpty() ? QString() : messageFor(m_result);
}

void CameraSession::start() {
    if (isActive()) {
        return;
    }
    delete m_request;
    m_request = m_mode == Mode::Enroll ? AuthdRequest::enroll(m_label, m_replace, true, this)
                                       : AuthdRequest::test(m_durationMs, true, this);
    connect(m_request, &AuthdRequest::started, this, [this] { setState(State::Running); });
    connect(m_request, &AuthdRequest::frameReceived, this, &CameraSession::onFrame);
    connect(m_request, &AuthdRequest::finished, this, &CameraSession::onFinished);

    resetFrame();
    m_result.clear();
    m_resultData.clear();
    m_request->start();
    setState(State::Waiting);
}

void CameraSession::cancel() {
    if (m_request != nullptr) {
        m_request->cancel();
    }
}

void CameraSession::reset() {
    delete m_request;
    m_request = nullptr;
    resetFrame();
    m_result.clear();
    m_resultData.clear();
    // always emitted: result and resultData share stateChanged, so even Idle to Idle may clear a result
    m_state = State::Idle;
    emit stateChanged();
}

void CameraSession::onFrame(const QJsonObject& report, const QImage& preview) {
    m_frameState = report.value(QStringLiteral("state")).toString();
    m_distance = numberOr(report.value(QStringLiteral("distance")), kNoValue);
    m_certainty = numberOr(report.value(QStringLiteral("certainty")), m_certainty);
    m_darkness = numberOr(report.value(QStringLiteral("darkness")), 0);
    m_darkThreshold = numberOr(report.value(QStringLiteral("dark_threshold")), m_darkThreshold);
    m_faces.clear();
    for (const QJsonValue& value : report.value(QStringLiteral("faces")).toArray()) {
        const QJsonArray box = value.toArray();
        if (box.size() == 4) {
            m_faces.append(
                QRectF(box.at(0).toDouble(), box.at(1).toDouble(), box.at(2).toDouble(), box.at(3).toDouble()));
        }
    }
    ++m_frameCount;
    emit frameChanged();

    // Previews come at most every 100 ms; frames in between keep showing the last one.
    if (!preview.isNull()) {
        m_preview = preview;
        emit previewChanged();
    }
}

void CameraSession::onFinished(const QString& result, const QJsonObject& data) {
    m_result = result;
    m_resultData = data.toVariantMap();
    m_request->deleteLater();
    m_request = nullptr;
    setState(State::Finished);
    emit finished(result);
}

void CameraSession::resetFrame() {
    m_frameState.clear();
    m_faces.clear();
    m_distance = kNoValue;
    m_certainty = kNoValue;
    m_darkness = 0;
    m_darkThreshold = 0;
    m_frameCount = 0;
    emit frameChanged();
    if (!m_preview.isNull()) {
        m_preview = {};
        emit previewChanged();
    }
}

void CameraSession::setState(const State state) {
    if (m_state != state) {
        m_state = state;
        emit stateChanged();
    }
}

auto CameraSession::messageFor(const QString& result) -> QString {
    if (result == QStringLiteral("success")) {
        return tr("Face model saved.");
    }
    if (result == QStringLiteral("completed")) {
        return tr("Test finished.");
    }
    if (result == QStringLiteral("no_face")) {
        return tr("No face was found. Look straight into the camera and try again.");
    }
    if (result == QStringLiteral("multiple_faces")) {
        return tr("More than one face was in view. Make sure only you are in front of the camera.");
    }
    if (result == QStringLiteral("too_dark")) {
        return tr("The picture was too dark. Add some light or check dark_threshold in the configuration.");
    }
    if (result == QStringLiteral("black_frames")) {
        return tr("The camera only delivered black frames. If it is an IR camera, its emitter may be off.");
    }
    if (result == QStringLiteral("model_mismatch")) {
        return tr("Your face models were made with a different recognizer. Enroll again to replace them.");
    }
    if (result == QStringLiteral("no_models")) {
        return tr("You have no face models yet. Enroll one first.");
    }
    if (result == QStringLiteral("invalid_device")) {
        return tr("The camera could not be opened. Check device_path in the configuration.");
    }
    if (result == QStringLiteral("preempted")) {
        return tr("A login needed the camera, so this was stopped. Try again when it is done.");
    }
    return ModelStore::messageFor(result);
}

} // namespace secureEye
