// frontend/src/components/SemanticSearchBar.jsx

import React from 'react';

const SemanticSearchBar = ({
  query,
  setQuery,
  handleSearch,
  loading,
  // We can ignore selectedFilters since we always do semantic
  resetSearch
}) => {
  const onSubmit = (e) => {
    e.preventDefault();
    handleSearch();
  };

  return (
    <form onSubmit={onSubmit} className="mb-3">
      <div className="mb-2">
        <div className="input-group">
          <input
            type="text"
            className="form-control me-2"
            placeholder="Ask your question..."
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
              <>
                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                Searching...
              </>
            ) : (
              'Search'
            )}
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-lg ms-2"
            style={{ minWidth: '90px' }}
            onClick={resetSearch}
            disabled={loading}
          >
            Reset
          </button>
        </div>
      </div>
    </form>
  );
};

export default SemanticSearchBar;
