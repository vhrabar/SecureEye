#include "ModelStore.hpp"

#include "AuthdRequest.hpp"

#include <QJsonArray>

namespace secureEye {

ModelStore::ModelStore(QObject* parent) : QAbstractListModel(parent) {}

// Requests are children; deleting them closes their connections.
ModelStore::~ModelStore() = default;

auto ModelStore::rowCount(const QModelIndex& parent) const -> int {
    return parent.isValid() ? 0 : count();
}

auto ModelStore::data(const QModelIndex& index, const int role) const -> QVariant {
    if (!index.isValid() || index.row() >= rowCount()) {
        return {};
    }
    const Row& row = m_rows.at(index.row());
    switch (role) {
    case ModelIdRole:
        return row.id;
    case Qt::DisplayRole:
    case LabelRole:
        return row.label;
    case CreatedRole:
        return row.created;
    case EmbeddingSpaceRole:
        return row.embeddingSpace;
    default:
        return {};
    }
}

auto ModelStore::roleNames() const -> QHash<int, QByteArray> {
    // "id" is reserved in QML, hence modelId
    return {
        {ModelIdRole, "modelId"},
        {LabelRole, "label"},
        {CreatedRole, "created"},
        {EmbeddingSpaceRole, "embeddingSpace"},
    };
}

auto ModelStore::user() const -> QString {
    return AuthdRequest::currentUser();
}

auto ModelStore::errorMessage() const -> QString {
    return m_error.isEmpty() ? QString() : messageFor(m_error);
}

void ModelStore::refresh() {
    delete m_listRequest;
    m_listRequest = AuthdRequest::modelsList(this);
    connect(m_listRequest, &AuthdRequest::finished, this, &ModelStore::onListFinished);
    m_listRequest->start();
    emit loadingChanged();
}

auto ModelStore::remove(const int modelId) -> bool {
    return startChange(AuthdRequest::modelsRemove(modelId, this));
}

auto ModelStore::clear() -> bool {
    return startChange(AuthdRequest::modelsClear(this));
}

auto ModelStore::startChange(AuthdRequest* request) -> bool {
    if (m_changeRequest != nullptr) {
        delete request;
        return false;
    }
    m_changeRequest = request;
    connect(request, &AuthdRequest::finished, this, [this, request](const QString& result, const QJsonObject&) {
        m_changeRequest = nullptr;
        request->deleteLater();
        emit busyChanged();
        if (result != QStringLiteral("success")) {
            emit operationFailed(result, messageFor(result));
        }
        // also after a failure: "no_models" or "model_not_found" mean the list was already out of date
        refresh();
    });
    request->start();
    emit busyChanged();
    return true;
}

void ModelStore::onListFinished(const QString& result, const QJsonObject& data) {
    m_listRequest->deleteLater();
    m_listRequest = nullptr;

    if (result == QStringLiteral("success")) {
        QList<Row> rows;
        for (const QJsonValue& value : data.value(QStringLiteral("models")).toArray()) {
            const QJsonObject model = value.toObject();
            rows.append({
                .id = model.value(QStringLiteral("id")).toInt(),
                .label = model.value(QStringLiteral("label")).toString(),
                .created = QDateTime::fromSecsSinceEpoch(model.value(QStringLiteral("time")).toInteger()),
                .embeddingSpace = model.value(QStringLiteral("model_id")).toString(),
            });
        }
        setRows(std::move(rows));
        setError({});
    } else {
        // stale rows would suggest the list is still current
        setRows({});
        setError(result);
    }
    emit loadingChanged();
}

void ModelStore::setRows(QList<Row> rows) {
    const int before = count();
    const int nextBefore = nextModelId();
    beginResetModel();
    m_rows = std::move(rows);
    endResetModel();
    if (count() != before) {
        emit countChanged();
    }
    if (nextModelId() != nextBefore) {
        emit nextModelIdChanged();
    }
}

void ModelStore::setError(const QString& error) {
    if (m_error != error) {
        m_error = error;
        emit errorChanged();
    }
}

auto ModelStore::messageFor(const QString& result) -> QString {
    if (result == QStringLiteral("daemon_unavailable")) {
        return tr("The SecureEye service is not running. Start it from the dashboard to manage face models.");
    }
    if (result == QStringLiteral("daemon_outdated")) {
        return tr("The SecureEye service is older than this app. Update SecureEye and restart the service.");
    }
    if (result == QStringLiteral("model_file_invalid")) {
        return tr("Your face model file cannot be read. Remove all models to start over.");
    }
    if (result == QStringLiteral("no_models")) {
        return tr("You have no face models.");
    }
    if (result == QStringLiteral("model_not_found")) {
        return tr("That face model no longer exists.");
    }
    if (result == QStringLiteral("busy")) {
        return tr("SecureEye is busy, for example with a login. Try again in a moment.");
    }
    if (result == QStringLiteral("forbidden")) {
        return tr("The SecureEye service refused to manage these face models.");
    }
    if (result == QStringLiteral("timeout")) {
        return tr("The SecureEye service did not answer in time.");
    }
    if (result == QStringLiteral("cancelled")) {
        return tr("Cancelled.");
    }
    return tr("Something went wrong in the SecureEye service (%1). The system journal has details.").arg(result);
}

} // namespace secureEye
