#ifndef SECUREEYE_CAMERASESSION_HPP
#define SECUREEYE_CAMERASESSION_HPP

#include <QImage>
#include <QJsonObject>
#include <QObject>
#include <QQmlEngine>
#include <QRectF>
#include <QString>
#include <QVariantList>
#include <QVariantMap>

namespace secureEye {

class AuthdRequest;

// A daemon-side camera session (enroll or test) as QML sees it
class CameraSession : public QObject {
    Q_OBJECT
    QML_ELEMENT

    // What start() asks for; changes while a session runs apply to the next one.
    Q_PROPERTY(Mode mode READ mode WRITE setMode NOTIFY modeChanged)
    // enroll: the new model's label, and whether it replaces the models of the active recognizer (re-enroll).
    Q_PROPERTY(QString label READ label WRITE setLabel NOTIFY labelChanged)
    Q_PROPERTY(bool replace READ replace WRITE setReplace NOTIFY replaceChanged)
    // test: how long to keep matching.
    Q_PROPERTY(int durationMs READ durationMs WRITE setDurationMs NOTIFY durationMsChanged)

    Q_PROPERTY(State state READ state NOTIFY stateChanged)
    // Between start() and the result; the camera may be on.
    Q_PROPERTY(bool active READ isActive NOTIFY stateChanged)

    // From the latest frame report (see docs/auth-protocol-v2.md).
    // "black", "dark", "no_face", "multiple", "face" or "match"; empty before the first frame.
    Q_PROPERTY(QString frameState READ frameState NOTIFY frameChanged)
    // Face boxes as QRectF fractions (0..1) of the preview image.
    Q_PROPERTY(QVariantList faces READ faces NOTIFY frameChanged)
    // Closest match in the frame on the config.ini certainty scale; NaN when nothing was compared.
    Q_PROPERTY(double distance READ distance NOTIFY frameChanged)
    Q_PROPERTY(double certainty READ certainty NOTIFY frameChanged)
    Q_PROPERTY(double darkness READ darkness NOTIFY frameChanged)
    Q_PROPERTY(double darkThreshold READ darkThreshold NOTIFY frameChanged)
    Q_PROPERTY(int frameCount READ frameCount NOTIFY frameChanged)
    Q_PROPERTY(bool hasPreview READ hasPreview NOTIFY previewChanged)

    // The session's result code once finished, e.g. "success", "no_face", "preempted" or "daemon_unavailable".
    Q_PROPERTY(QString result READ result NOTIFY stateChanged)
    Q_PROPERTY(QString resultMessage READ resultMessage NOTIFY stateChanged)
    // The result's data object, e.g. {model, label} after an enrollment or {matched_frames, best_distance} after a
    // test.
    Q_PROPERTY(QVariantMap resultData READ resultData NOTIFY stateChanged)

public:
    enum class Mode {
        Enroll,
        Test,
    };
    Q_ENUM(Mode)

    enum class State {
        Idle,     // never started
        Waiting,  // connecting, or waiting for the camera
        Running,  // the daemon has the camera; frames are arriving
        Finished, // result is set
    };
    Q_ENUM(State)

    explicit CameraSession(QObject* parent = nullptr);
    ~CameraSession() override;

    [[nodiscard]] auto mode() const -> Mode {
        return m_mode;
    }
    void setMode(Mode mode);
    [[nodiscard]] auto label() const -> QString {
        return m_label;
    }
    void setLabel(const QString& label);
    [[nodiscard]] auto replace() const -> bool {
        return m_replace;
    }
    void setReplace(bool replace);
    [[nodiscard]] auto durationMs() const -> int {
        return m_durationMs;
    }
    void setDurationMs(int durationMs);

    [[nodiscard]] auto state() const -> State {
        return m_state;
    }
    [[nodiscard]] auto isActive() const -> bool {
        return m_state == State::Waiting || m_state == State::Running;
    }
    [[nodiscard]] auto frameState() const -> QString {
        return m_frameState;
    }
    [[nodiscard]] auto faces() const -> QVariantList {
        return m_faces;
    }
    [[nodiscard]] auto distance() const -> qreal {
        return m_distance;
    }
    [[nodiscard]] auto certainty() const -> qreal {
        return m_certainty;
    }
    [[nodiscard]] auto darkness() const -> qreal {
        return m_darkness;
    }
    [[nodiscard]] auto darkThreshold() const -> qreal {
        return m_darkThreshold;
    }
    [[nodiscard]] auto frameCount() const -> int {
        return m_frameCount;
    }
    [[nodiscard]] auto hasPreview() const -> bool {
        return !m_preview.isNull();
    }
    [[nodiscard]] auto preview() const -> const QImage& {
        return m_preview;
    }
    [[nodiscard]] auto result() const -> QString {
        return m_result;
    }
    [[nodiscard]] auto resultMessage() const -> QString;
    [[nodiscard]] auto resultData() const -> QVariantMap {
        return m_resultData;
    }

    // Start a session with the current mode and settings. Does nothing while one is active.
    Q_INVOKABLE void start();
    // Stop the session and give the camera back. The result still arrives through stateChanged.
    Q_INVOKABLE void cancel();
    // Back to Idle with no frame, preview or result. A running session is dropped by closing its connection, which
    // the daemon takes as a cancel; no result is reported for it. For dialogs that are closed and opened again.
    Q_INVOKABLE void reset();

    // A user-facing sentence for a session result, on top of ModelStore::messageFor().
    // moc cannot parse trailing return types, so the invokables spell theirs out.
    [[nodiscard]] Q_INVOKABLE static QString messageFor(const QString& result);

signals:
    void modeChanged();
    void labelChanged();
    void replaceChanged();
    void durationMsChanged();
    void stateChanged();
    void frameChanged();
    void previewChanged();
    // The session ended; result and resultData are set.
    void finished(const QString& result);

private:
    void onFrame(const QJsonObject& report, const QImage& preview);
    void onFinished(const QString& result, const QJsonObject& data);
    void resetFrame();
    void setState(State state);

    Mode m_mode = Mode::Enroll;
    QString m_label;
    bool m_replace = false;
    int m_durationMs = 15000;

    State m_state = State::Idle;
    AuthdRequest* m_request = nullptr;

    QString m_frameState;
    QVariantList m_faces;
    qreal m_distance;
    qreal m_certainty;
    qreal m_darkness = 0;
    qreal m_darkThreshold = 0;
    int m_frameCount = 0;
    QImage m_preview;

    QString m_result;
    QVariantMap m_resultData;
};

} // namespace secureEye

#endif // SECUREEYE_CAMERASESSION_HPP
