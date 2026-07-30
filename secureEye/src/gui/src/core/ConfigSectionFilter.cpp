#include "ConfigSectionFilter.hpp"

#include "ConfigModel.hpp"

namespace secureEye {

ConfigSectionFilter::ConfigSectionFilter(QObject* parent) : QSortFilterProxyModel(parent) {}

void ConfigSectionFilter::setSection(const QString& section) {
    if (m_section == section) {
        return;
    }

    m_section = section;
#if QT_VERSION >= QT_VERSION_CHECK(6, 9, 0)
    beginFilterChange();
    endFilterChange(Direction::Rows);
#else
    invalidateRowsFilter();
#endif
    emit sectionChanged();
}

auto ConfigSectionFilter::filterAcceptsRow(const int sourceRow, const QModelIndex& sourceParent) const -> bool {
    if (sourceModel() == nullptr) {
        return false;
    }

    const QModelIndex index = sourceModel()->index(sourceRow, 0, sourceParent);

    return index.data(ConfigModel::SectionRole).toString() == m_section;
}

} // namespace secureEye
