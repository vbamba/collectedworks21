// frontend/src/components/SearchBar.jsx

import React, { useState } from 'react';

const SearchBar = ({ query, setQuery, handleSearch, loading, selectedFilters, setSelectedFilters }) => {
    const [searchType, setSearchType] = useState('all');

    const onSubmit = (e) => {
        e.preventDefault();
        handleSearch();
    };

    const handleSearchTypeChange = (value) => {
        const newSearchType = searchType === value ? 'all' : value;
        setSearchType(newSearchType);
        setSelectedFilters({ ...selectedFilters, search_type: newSearchType });
    };

    return (
        <form onSubmit={onSubmit} className="mb-3">
            <div className="mb-2">
                <div className="input-group">
                    <input
                        type="text"
                        className="form-control me-2"
                        placeholder="Enter your search query..."
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyPress={(e) => {
                            if (e.key === 'Enter') {
                                handleSearch();
                            }
                        }}
                        style={{ height: '38px' }}
                    />
                    <button 
                        className="btn btn-primary btn-lg"
                        onClick={handleSearch}
                        disabled={loading}
                        style={{ minWidth: '120px' }}
                    >
                        {loading ? (
                            <span>
                                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                                Searching...
                            </span>
                        ) : (
                            'Search'
                        )}
                    </button>
                </div>
            </div>

            {/* Search Type Filter on new row */}
            <div className="row">
                <div className="col d-flex gap-4">
                    <div className="form-check">
                        <input
                            type="checkbox"
                            className="form-check-input"
                            id="exact"
                            value="exact"
                            checked={searchType === 'exact'}
                            onChange={(e) => handleSearchTypeChange(e.target.value)}
                            name="search_type"
                        />
                        <label className="form-check-label" htmlFor="exact">
                            Exact Match
                        </label>
                    </div>
                    <div className="form-check">
                        <input
                            type="checkbox"
                            className="form-check-input"
                            id="all_words"
                            value="all_words"
                            checked={searchType === 'all_words'}
                            onChange={(e) => handleSearchTypeChange(e.target.value)}
                            name="search_type"
                        />
                        <label className="form-check-label" htmlFor="all_words">
                            All Words
                        </label>
                    </div>
                    <div className="form-check">
                        <input
                            type="checkbox"
                            className="form-check-input"
                            id="semantic"
                            value="semantic"
                            checked={searchType === 'semantic'}
                            onChange={(e) => handleSearchTypeChange(e.target.value)}
                            name="search_type"
                        />
                        <label className="form-check-label" htmlFor="semantic">
                            Ask a Question
                        </label>
                    </div>
                </div>
            </div>
        </form>
    );
};

export default SearchBar;
