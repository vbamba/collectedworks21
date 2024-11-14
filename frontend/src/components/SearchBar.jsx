// frontend/src/components/SearchBar.jsx

import React from 'react';

const SearchBar = ({ query, setQuery, handleSearch }) => {
    const onSubmit = (e) => {
        e.preventDefault();
        handleSearch();
    };

    return (
        <form onSubmit={onSubmit} className="mb-3">
            <div className="input-group">
                <input
                    type="text"
                    className="form-control"
                    placeholder="Enter your search query..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />
                <button type="submit" className="btn btn-primary">
                    Search
                </button>
            </div>
        </form>
    );
};

export default SearchBar;
