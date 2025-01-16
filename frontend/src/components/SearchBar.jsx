// frontend/src/components/SearchBar.jsx

import React, { useState, useEffect } from 'react';

const SearchBar = ({
  query,
  setQuery,
  handleSearch,
  loading,
  selectedFilters,
  setSelectedFilters,
  showSearchTypeControls = true, // NEW PROP
  onReset
}) => {
  // We derive local state from selectedFilters.search_type
  const [searchType, setSearchType] = useState(selectedFilters.search_type || 'all');

  useEffect(() => {
    // Keep local 'searchType' in sync if selectedFilters changes externally
    setSearchType(selectedFilters.search_type || 'all');
  }, [selectedFilters]);

  const onSubmit = (e) => {
    e.preventDefault();
    handleSearch();
  };

  const handleSearchTypeChange = (value) => {
    const newSearchType = searchType === value ? 'all' : value;
    setSearchType(newSearchType);
    setSelectedFilters({
      ...selectedFilters,
      search_type: newSearchType,
    });
  };

  const handleReset = () => {
    // Clears the search text and resets the filters
    if (onReset) {
      onReset();
    }
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
            className="btn btn-primary btn-search"
            onClick={handleSearch}
            disabled={loading}
          >
            {loading ? (
              <>
                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                Searching...
              </>
            ) : (
              'Search'
            )}
          </button>

          {/* Reset Button */}
          <button
            type="button"
            className="btn btn-secondary btn-reset ms-2"
            onClick={handleReset}
            disabled={loading}
          >
            Reset
          </button>
        </div>
      </div>

      {/* Conditionally show checkboxes if showSearchTypeControls === true */}
      {showSearchTypeControls && (
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
      )}
    </form>
  );
};

export default SearchBar;
