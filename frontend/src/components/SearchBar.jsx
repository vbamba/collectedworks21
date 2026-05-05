import React, { useState, useEffect, useRef } from 'react';
import { Tooltip } from 'react-tooltip';

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
  onReset,
  // CHANGED: focusKey — when this prop changes, focus the search input.
  // Pages pass `useLocation().state?.focusInput` (a Date.now() stamp the
  // NavBar attaches to its Search/Question links), so each navbar click
  // re-focuses the input even when the user is already on the page and
  // the component doesn't remount.
  focusKey,
}) => {
  // Local state for which checkbox is active
  const [searchType, setSearchType] = useState(selectedFilters.search_type || 'all');

  // CHANGED: ref to the query input + an effect that focuses it on mount
  // and on every focusKey change. Mount-focus covers fresh navigation
  // (different component → remount); focusKey covers re-clicks on the
  // same nav link when the page is already open.
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, [focusKey]);

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
            ref={inputRef}
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

          {/* CHANGED: removed inline "Ask a Question" link — the global
              NavBar's "Question" entry covers this now, and rendering it
              here as well duplicated the same destination next to the
              Clear button. The `hideSemantic` prop is preserved in case
              other call sites still pass it for the checkbox branch. */}
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
