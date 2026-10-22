#ifndef SECUREEYE_MODELSTORE_HPP
#define SECUREEYE_MODELSTORE_HPP

#include <QAbstractListModel>
#include <QDateTime>
#include <QJsonObject>
#include <QList>
#include <QQmlEngine>
#include <QString>

namespace secureEye {

class AuthdRequest;

// The face models enrolled for the user running the GUI, as listed by secureeye-authd (models_list).
//
class ModelStore : public QAbstractListModel {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(QString user READ user CONSTANT)
    Q_PROPERTY(int count READ count NOTIFY countChanged)
    // A models_list request is running.
    Q_PROPERTY(bool loading READ isLoading NOTIFY loadingChanged)
    // A remove or clear is running; further changes are refused until it finishes.
    Q_PROPERTY(bool busy READ isBusy NOTIFY busyChanged)
    // Result code of the last failed load, e.g. "daemon_unavailable" or "model_file_invalid"; empty after a
    // successful one. The rows are emptied while it is set.
    Q_PROPERTY(QString error READ error NOTIFY errorChanged)
    Q_PROPERTY(QString errorMessage READ errorMessage NOTIFY errorChanged)

public:
    enum Role : int {
        ModelIdRole = Qt::UserRole,
        LabelRole,
        CreatedRole,
        EmbeddingSpaceRole,
    };
    Q_ENUM(Role)

    explicit ModelStore(QObject* parent = nullptr);
    ~ModelStore() override;

    [[nodiscard]] auto rowCount(const QModelIndex& parent = {}) const -> int override;
    [[nodiscard]] auto data(const QModelIndex& index, int role) const -> QVariant override;
    [[nodiscard]] auto roleNames() const -> QHash<int, QByteArray> override;

    [[nodiscard]] auto user() const -> QString;
    [[nodiscard]] auto count() const -> int {
        return static_cast<int>(m_rows.size());
    }
    [[nodiscard]] auto isLoading() const -> bool {
        return m_listRequest != nullptr;
    }
    [[nodiscard]] auto isBusy() const -> bool {
        return m_changeRequest != nullptr;
    }
    [[nodiscard]] auto error() const -> QString {
        return m_error;
    }
    [[nodiscard]] auto errorMessage() const -> QString;

    // Reload the list. A load that is still running is dropped.
    Q_INVOKABLE void refresh();
    // Remove one model by its id. Returns false, and does nothing, while another change is running.
    // moc cannot parse trailing return types, so the invokables spell theirs out.
    Q_INVOKABLE bool remove(int modelId);
    // Remove every model, including an unreadable model file. Same rules as remove().
    Q_INVOKABLE bool clear();

    // A user-facing sentence for a result code from the daemon or AuthdRequest.
    [[nodiscard]] Q_INVOKABLE static QString messageFor(const QString& result);

signals:
    void countChanged();
    void loadingChanged();
    void busyChanged();
    void errorChanged();
    // A remove or clear did not succeed. The list is reloaded either way.
    void operationFailed(const QString& code, const QString& message);

private:
    struct Row {
        int id = 0;
        QString label;
        QDateTime created;
        QString embeddingSpace;
    };

    auto startChange(AuthdRequest* request) -> bool;
    void onListFinished(const QString& result, const QJsonObject& data);
    void setRows(QList<Row> rows);
    void setError(const QString& error);

    QList<Row> m_rows;
    QString m_error;
    AuthdRequest* m_listRequest = nullptr;
    AuthdRequest* m_changeRequest = nullptr;
};

} // namespace secureEye

#endif // SECUREEYE_MODELSTORE_HPP
