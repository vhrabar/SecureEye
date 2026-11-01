#include "ConfigSectionFilter.hpp"

#include "ConfigModel.hpp"

namespace secureEye {

ConfigSectionFilter::ConfigSectionFilter(QObject* parent) : QSortFilterProxyModel(parent) {}

void ConfigSectionFilter::setSection(const QString& section) {
    if (m_section == section) {
        return;
    }

    m_section = section;
    refilter();
    emit sectionChanged();
}

void ConfigSectionFilter::setAdvanced(const bool advanced) {
    if (m_advanced == advanced) {
        return;
    }

    m_advanced = advanced;
    refilter();
    emit advancedChanged();
}

void ConfigSectionFilter::refilter() {
#if QT_VERSION >= QT_VERSION_CHECK(6, 9, 0)
    beginFilterChange();
    endFilterChange(Direction::Rows);
#else
    invalidateRowsFilter();
#endif
}

auto ConfigSectionFilter::filterAcceptsRow(const int sourceRow, const QModelIndex& sourceParent) const -> bool {
    if (sourceModel() == nullptr) {
        return false;
    }

    const QModelIndex index = sourceModel()->index(sourceRow, 0, sourceParent);

    return index.data(ConfigModel::SectionRole).toString() == m_section &&
           index.data(ConfigModel::AdvancedRole).toBool() == m_advanced;
}

} // namespace secureEye
