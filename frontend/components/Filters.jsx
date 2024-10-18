// frontend/src/components/Filters.jsx
import React from 'react';

const Filters = ({ filters, selectedFilters, setSelectedFilters }) => {
    const handleChange = (e) => {
        const { name, value } = e.target;
        setSelectedFilters({ ...selectedFilters, [name]: value });
    };

    return (
        <div className="row mb-3">
            <div className="col-md-4">
                <select
                    name="author"
                    className="form-select"
                    value={selectedFilters.author}
                    onChange={handleChange}
                >
                    <option value="">All Authors</option>
                    {filters.authors.map((author, index) => (
                        <option key={index} value={author}>
                            {author}
                        </option>
                    ))}
                </select>
            </div>
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
                            {group}
                        </option>
                    ))}
                </select>
            </div>
            <div className="col-md-4">
                <select
                    name="book_title"
                    className="form-select"
                    value={selectedFilters.book_title}
                    onChange={handleChange}
                >
                    <option value="">All Book Titles</option>
                    {filters.book_titles.map((title, index) => (
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
