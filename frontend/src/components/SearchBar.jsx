import React, { useState, useEffect } from 'react';
import { Tooltip } from 'react-tooltip';
import { Link } from 'react-router-dom'; // ← Added for hyperlink navigation

/**
 * A reusable search bar that supports:
 *  - query input
 *  - Search / Clear buttons
 *  - Optional Exact Match and Semantic checkboxes
 *
 * Props:
 *  - query, setQuery: controlled input value & setter
 *  - handleSearch: callback to actually perform the search
 *  - loading: boolean, whether a search is in progress
 *  - selectedFilters, setSelectedFilters: holds filter state, including search_type
 *  - showSearchTypeControls: whether to render Exact Match checkbox at all
 *  - hideSemantic: when true, omits the “Ask a Question (AI)” checkbox and shows link
 *  - onReset: optional reset callback
 */
const SearchBar = ({
  query,
  setQuery,
  handleSearch,
  loading,
  selectedFilters,
  setSelectedFilters,
  showSearchTypeControls = true,
  hideSemantic = false,
  onReset
}) => {
  // Local state for which checkbox is active
  const [searchType, setSearchType] = useState(selectedFilters.search_type || 'all');

  // Sync local searchType with props
  useEffect(() => {
    setSearchType(selectedFilters.search_type || 'all');
  }, [selectedFilters]);

  // Handle form submit (Enter key)
  const onSubmit = (e) => {
    e.preventDefault();
    handleSearch();
  };

  // Toggle Exact or Semantic
  const handleSearchTypeChange = (value) => {
    const newType = searchType === value ? 'all' : value;
    setSearchType(newType);
    setSelectedFilters({
      ...selectedFilters,
      search_type: newType,
    });
  };

  // Invoke parent reset if provided
  const handleReset = () => {
    if (onReset) onReset();
  };

  return (
    <form onSubmit={onSubmit} className="mb-3">
      <div className="mb-2">
        <div className="input-group align-items-center">
          {/* Query input */}
          <input
            type="text"
            className="form-control"
            placeholder="Enter your search query..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => { if (e.key === 'Enter') handleSearch(); }}
            style={{
              height: '38px',
              flex: '1 1 auto',         // Flexible width
              minWidth: '24ch'          // ~4-5 words on mobile
            }}
          />

          {/* Exact Match inline */}
          {showSearchTypeControls && (
            <div className="input-group-text d-flex align-items-center ms-2">
              <input
                type="checkbox"
                className="form-check-input mt-0"
                id="exact"
                value="exact"
                checked={searchType === 'exact'}
                onChange={(e) => handleSearchTypeChange(e.target.value)}
                name="search_type"
              />
              <label className="form-check-label mb-0 ms-1" htmlFor="exact">
                Exact Match
              </label>
            </div>
          )}

          {/* Search button */}
          <button
            className="btn btn-primary btn-search ms-2"
            onClick={handleSearch}
            disabled={loading}
          >
            {loading ? (
              <>
                <span
                  className="spinner-border spinner-border-sm me-1"
                  role="status"
                  aria-hidden="true"
                ></span>
                Searching...
              </>
            ) : 'Search'}
          </button>

          {/* Clear button */}
          <button
            type="button"
            className="btn btn-secondary btn-reset ms-2"
            onClick={handleReset}
            disabled={loading}
          >
            Clear
          </button>

          {/* Ask a Question link if hiding semantic */}
          {hideSemantic && (
            <Link
              to="/question"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-link ms-2"
            >
              Ask a Question
            </Link>
          )}
        </div>
      </div>

      {/* Semantic / AI assistant checkbox below */}
      {!hideSemantic && showSearchTypeControls && (
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
            <span
              data-tooltip-id="semantic-tooltip"
              style={{ cursor: 'pointer', color: '#0d6efd' }} /* Bootstrap primary for dark theme */
            >
              Ask a Question (AI assistant)?
            </span>
            <Tooltip
              id="semantic-tooltip"
              place="top"
              variant="dark"
              content={
                <>
                  This option uses AI to<br />
                  answer your query rather<br />
                  than matching exact words.
                </>
              }
            />
          </label>
        </div>
      )}
    </form>
  );
};

export default SearchBar;
