// frontend/src/pages/TextSearchPage.jsx

import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useLocation } from 'react-router-dom';
import { debounce }                     from 'lodash';

import SearchBar                        from '../components/SearchBar';
import Filters                          from '../components/Filters';
// CHANGED: Removed import of BookAccordion since we're no longer grouping by book
import TextResultCard                   from '../components/TextResultCard';
import { fetchFilters, performTextSearch } from '../services/api';

const TextSearchPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  // CHANGED: pick up the focusInput stamp NavBar attaches to its Search
  // link's `state` so SearchBar re-focuses its input on every nav click.
  const location = useLocation();

  // ── Controlled inputs & filters
  const [query, setQuery] = useState('');
  const [filtersData, setFiltersData] = useState({
    authors: [], groups: [], book_titles: [], book_titles_by_group: {}
  });
  const [selectedFilters, setSelectedFilters] = useState({
    author: '', group: '', book_title: '', search_type: 'all'
  });

  // ── Results & UI state
  const [allResults, setAllResults]   = useState([]);
  const [groupCounts, setGroupCounts] = useState({});
  const [activeGroup, setActiveGroup] = useState('');
  const [activeBook,  setActiveBook]  = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const resultsPerPage = 20;
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState('');

  // 1️⃣ Load filter options once
  useEffect(() => {
    fetchFilters()
      .then(data => setFiltersData(data))
      .catch(() => setError('Failed to load filters.'));
  }, []);

  // 2️⃣ Sync URL → state whenever the query or filters change
  useEffect(() => {
    const q          = searchParams.get('query')       || '';
    const author     = searchParams.get('author')      || '';
    const group      = searchParams.get('group')       || '';
    const book_title = searchParams.get('book_title')  || '';
    const search_type= searchParams.get('search_type') || 'all';

    setQuery(q);
    setSelectedFilters({ author, group, book_title, search_type });

    if (q.trim()) {
      debouncedSearch(q, { author, group, book_title, search_type });
    } else {
      setAllResults([]);
      setGroupCounts({});
      setActiveGroup('');
      setActiveBook('');
      setCurrentPage(1);
    }
  }, [searchParams]);

  // 3️⃣ Debounced API call
  const debouncedSearch = useMemo(
    () => debounce(async (q, flt) => {
      setLoading(true);
      setError('');
      try {
        const data = await performTextSearch(q, flt);
        setAllResults(data.results || []);
        setGroupCounts(data.group_counts || {});
        setActiveGroup('');   // reset the in-page chip selection on new search
        setActiveBook('');
        setCurrentPage(1);
      } catch {
        setError('Search failed. Try again.');
      }
      setLoading(false);
    }, 300),
    []
  );

  // 4️⃣ When the user clicks “Search”
  const handleSearch = () => {
    const { author, group, book_title, search_type } = selectedFilters;
    setSearchParams({ query, author, group, book_title, search_type });
  };

  // 5️⃣ When the user clicks “Clear”
  const handleReset = () => {
    setQuery('');
    setSelectedFilters({ author:'', group:'', book_title:'', search_type:'all' });
    setSearchParams({});
    setAllResults([]);
    setGroupCounts({});
    setActiveGroup('');
    setActiveBook('');
    setCurrentPage(1);
  };

  // CHANGED: introduce an "effectiveGroup" that prefers the in-page chip (activeGroup),
  //          but falls back to the dropdown filter (selectedFilters.group) if set.
  //          This lets us 1) hide Books list when *neither* is chosen,
  //          and 2) still scope book counts when only the dropdown is set.
  const effectiveGroup = activeGroup || selectedFilters.group || '';

  // ── Facet counts ──────────────────────────────────────────────────────────────

  // How many hits per book (respecting an effectiveGroup)
  const bookCounts = useMemo(() => {
    const counts = {};
    allResults.forEach(r => {
      // CHANGED: filter by effectiveGroup instead of activeGroup only
      if (effectiveGroup && r.group !== effectiveGroup) return;
      counts[r.book_title] = (counts[r.book_title] || 0) + 1;
    });
    return counts;
  }, [allResults, effectiveGroup]);

  // CHANGED: Calculate total number of results for books facet,
  //          scoped to effectiveGroup only (if present)
  const totalBookResultsCount = useMemo(() => {
    return allResults.filter(r => !effectiveGroup || r.group === effectiveGroup).length;
  }, [allResults, effectiveGroup]);

  // ── In-page filtering & pagination ─────────────────────────────────────────────

  // 1) Filter by effectiveGroup & activeBook
  const displayedResults = useMemo(() => {
    return allResults
      .filter(r => !effectiveGroup || r.group === effectiveGroup) // CHANGED
      .filter(r => !activeBook  || r.book_title === activeBook);
  }, [allResults, effectiveGroup, activeBook]);

  // 2) Pagination
  const totalPages = Math.ceil(displayedResults.length / resultsPerPage);
  const startIdx   = (currentPage - 1) * resultsPerPage;
  const pageResults= displayedResults.slice(startIdx, startIdx + resultsPerPage);

  // Handlers for the facet buttons
  const handleCollectionClick = grp => {
    setActiveGroup(grp);   // CHANGED: this drives effectiveGroup
    setActiveBook('');
    setCurrentPage(1);
  };
  const handleBookClick = book => {
    setActiveBook(book);
    setCurrentPage(1);
  };
  const handlePageChange = page => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="homepage-container">
      {/* CHANGED: removed the per-page <header> with logo + heading. Site
          identity now lives in the global NavBar (App.js → NavBar.jsx),
          which also gives chapter pages a way to switch books. */}

      {/* Search + Clear */}
      <SearchBar
        query={query}
        setQuery={setQuery}
        handleSearch={handleSearch}
        loading={loading}
        selectedFilters={selectedFilters}
        setSelectedFilters={setSelectedFilters}
        showSearchTypeControls
        hideSemantic
        onReset={handleReset}
        focusKey={location.state?.focusInput}
      />

      {/* Dropdown filters */}
      <Filters
        filters={filtersData}
        selectedFilters={selectedFilters}
        setSelectedFilters={setSelectedFilters}
      />

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {/* Collections Found row (only if no filter-by-collection/book_title) */}
      {!selectedFilters.group &&
       !selectedFilters.book_title &&
       Object.entries(groupCounts).length > 0 && (
        <div className="mb-2">
          <strong>Collections Found:</strong>{' '}
          <button
            className={`btn btn-sm ${!activeGroup ? 'btn-primary' : 'btn-outline-primary'} me-1`}
            onClick={() => handleCollectionClick('')}
          >
            All Collections ({allResults.length})
          </button>
          {Object.entries(groupCounts).map(([grp, cnt]) => (
            <button
              key={grp}
              className={`btn btn-sm ${
                activeGroup === grp ? 'btn-primary' : 'btn-outline-primary'
              } me-1`}
              onClick={() => handleCollectionClick(grp)}
            >
              {grp} ({cnt})
            </button>
          ))}
        </div>
      )}

      {/* Books Found row
          CHANGED: show ONLY if a collection is selected (either via dropdown or chip).
          I.e., hide when "All Collections" is active (effectiveGroup is empty). */}
      {!!effectiveGroup &&                 /* CHANGED: require some collection */
       !selectedFilters.book_title &&
       Object.entries(bookCounts).length > 0 && (
        <div className="mb-3">
          <strong>Books Found:</strong>{' '}
          <button
            className={`btn btn-sm ${!activeBook ? 'btn-primary' : 'btn-outline-primary'} me-1`}
            onClick={() => handleBookClick('')}
          >
            {/* CHANGED: Use totalBookResultsCount scoped by effectiveGroup */}
            All Books ({totalBookResultsCount})
          </button>
          {Object.entries(bookCounts).map(([title, cnt]) => (
            <button
              key={title}
              className={`btn btn-sm ${
                activeBook === title ? 'btn-primary' : 'btn-outline-primary'
              } me-1`}
              onClick={() => handleBookClick(title)}
            >
              {title} ({cnt})
            </button>
          ))}
        </div>
      )}

      {/* ── DISPLAY RESULTS AS A FLAT LIST ──────────────────────────────────────── */}
      <div className="results-list">
        {loading ? (
          <div className="text-center my-4">
            <div className="spinner-border" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : pageResults.length > 0 ? (
          <>
            {/* Render each result in the order returned, without grouping */}
            {pageResults.map((res, idx) => (
              <TextResultCard
                key={`${res.section_filename || 'result'}-${idx}`}
                result={res}
                // CHANGED: Always pass singleResult={true} so title becomes "Book Name - Chapter Name"
                bookTitle={res.book_title}
                singleResult={true}
                query={query}
                searchType={selectedFilters.search_type}
              />
            ))}

            {/* Pagination */}
            {totalPages > 1 && (
              <nav aria-label="Search results pages" className="mt-4">
                <ul className="pagination justify-content-center">
                  <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                    <button
                      className="page-link"
                      onClick={() => handlePageChange(currentPage - 1)}
                    >
                      Previous
                    </button>
                  </li>
                  {Array.from({ length: totalPages }, (_, i) => (
                    <li
                      key={i + 1}
                      className={`page-item ${currentPage === i + 1 ? 'active' : ''}`}
                    >
                      <button
                        className="page-link"
                        onClick={() => handlePageChange(i + 1)}
                      >
                        {i + 1}
                      </button>
                    </li>
                  ))}
                  <li
                    className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}
                  >
                    <button
                      className="page-link"
                      onClick={() => handlePageChange(currentPage + 1)}
                    >
                      Next
                    </button>
                  </li>
                </ul>
              </nav>
            )}
          </>
        ) : (
          !loading && <p>No results found.</p>
        )}
      </div>
    </div>
  );
};

export default TextSearchPage;
