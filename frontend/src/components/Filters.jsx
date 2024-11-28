// frontend/src/components/Filters.jsx

import React, { useEffect } from 'react';

const Filters = ({ filters, selectedFilters, setSelectedFilters }) => {
    const handleChange = (e) => {
        const { name, value } = e.target;
        setSelectedFilters({ ...selectedFilters, [name]: value });
    };
  

    // Display book titles based on selected group or default to all sorted titles
    const filteredBooks = selectedFilters.group
        ? filters.book_titles_by_group[selectedFilters.group] || []
        : filters.book_titles;

    // Group descriptions mapping for display
    const groupDescriptions = {
        CWSA: "Collected Works of Sri Aurobindo",
        CWM: "Collected Works of The Mother",
        Disciples: "Works of Disciples"
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
                    <option value="">All Groups</option>
                    {filters.groups.map((group, index) => (
                        <option key={index} value={group}>
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
                    {filteredBooks.map((title, index) => (
                        <option key={index} value={title}>
                            {title}
                        </option>
                    ))}
                </select>
            </div>



        </div>
    );
};

export default Filters;
