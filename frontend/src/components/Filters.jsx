// frontend/src/components/Filters.jsx

import React from 'react';

// CHANGED (2026-07-11): added Compilations (joint Sri Aurobindo & Mother
// compilation volumes) as its own collection shelf.
const collectionOrder = ['CWSA','CWM','Agenda','Compilations','Disciples'];

const Filters = ({ filters, selectedFilters, setSelectedFilters }) => {
  const handleChange = (e) => {
    const { name, value } = e.target;

    // FIX: When changing collection, also clear the book_title to avoid stale selection
    if (name === 'group') {
      setSelectedFilters((prev) => ({ ...prev, group: value, book_title: '' }));
      return;
    }

    setSelectedFilters((prev) => ({ ...prev, [name]: value }));
  };

  // Group descriptions mapping for display
  const groupDescriptions = {
    CWSA: 'Collected Works of Sri Aurobindo',
    CWM: 'Collected Works of The Mother',
    Agenda: 'Agenda',
    // CHANGED (2026-07-11): label for the new Compilations group
    Compilations: 'Compilations',
    Disciples: 'Works of Disciples',
  };

  // ENSURE ORDER: Sort the groups dropdown by desired collection order
  const groupsSorted = (filters.groups || [])
    .slice()
    .sort(
      (a, b) => collectionOrder.indexOf(a) - collectionOrder.indexOf(b)
    );

  // FIX: If a collection is selected, only render that collection's optgroup
  const groupsToShow = selectedFilters.group
    ? [selectedFilters.group]
    : collectionOrder;

  // Dark-theme friendly optgroup label (slightly brighter for contrast, not pure white)
  const optgroupStyle = {
    color: '#d9d9d9',     // suitable for dark theme; readable but not stark white
    fontWeight: 700,
    letterSpacing: '0.02em',
  };

  return (
    <div className="row mb-3">
      {/* Group Filter */}
      <div className="col-md-4">
        <select
          name="group"
          className="form-select"
          value={selectedFilters.group}
          onChange={handleChange}
        >
          <option value="">All Collections</option>
          {groupsSorted.map((group) => (
            <option key={group} value={group}>
              {groupDescriptions[group] || group}
            </option>
          ))}
        </select>
      </div>

      {/* Book Title Filter (Filtered based on selected group) */}
      <div className="col-md-4">
        <select
          name="book_title"
          className="form-select"
          value={selectedFilters.book_title}
          onChange={handleChange}
        >
          <option value="">All Book Titles</option>

          {groupsToShow.map((coll) => {
            const titles = (filters.book_titles_by_group?.[coll] || []);
            if (!titles.length) return null;

            return (
              <optgroup
                key={coll}
                label={groupDescriptions[coll]}
                style={optgroupStyle} // darker (higher-contrast) label on dark theme
              >
                {titles.map((title) => (
                  <option key={title} value={title}>
                    {title}
                  </option>
                ))}
              </optgroup>
            );
          })}
        </select>
      </div>
    </div>
  );
};

export default Filters;
