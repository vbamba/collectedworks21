// frontend/src/pages/SearchPage.jsx

import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { debounce } from 'lodash';
import SearchBar from '../components/SearchBar';
import Filters from '../components/Filters';
import BookAccordion from '../components/BookAccordion';
import ResultCard from '../components/ResultCard';
import { fetchFilters, performSearch } from '../services/api';

const SearchPage = ({
  heading = 'Search Works of Sri Aurobindo and The Mother',
  defaultSearchType = 'all',
  showSearchTypeControls = true
}) => {
  const [searchParams, setSearchParams] = useSearchParams();

  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({
    authors: [],
    groups: [],
    book_titles: [],
    book_titles_by_group: {},
  });
  // We track the selected filters, forcing 'search_type' = defaultSearchType initially
  const [selectedFilters, setSelectedFilters] = useState({
    author: '',
    group: '',
    book_title: '',
    search_type: defaultSearchType, 
  });

  const [allResults, setAllResults] = useState([]);
  const [groupCounts, setGroupCounts] = useState({});
  const [activeGroup, setActiveGroup] = useState('');

  const [currentPage, setCurrentPage] = useState(1);
  const resultsPerPage = 10;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Fetch filters on mount
  useEffect(() => {
    const getFilters = async () => {
      try {
        const data = await fetchFilters();
        const authorOrder = ['Sri Aurobindo', 'The Mother', 'Disciples'];
        const sortedAuthors = authorOrder.filter(author => data.authors.includes(author));

        setFilters({
          ...data,
          authors: sortedAuthors,
        });
      } catch (err) {
        console.error('Error fetching filters:', err);
        setError('Failed to load filters.');
      }
    };
    getFilters();
  }, []);

  // When the component mounts or searchParams changes, parse them
  useEffect(() => {
    const urlQuery = searchParams.get('query') || '';
    const author = searchParams.get('author') || '';
    const group = searchParams.get('group') || '';
    const book_title = searchParams.get('book_title') || '';
    // If user tries to override search_type in the URL, we can either accept or override
    const st = searchParams.get('search_type') || defaultSearchType;

    setQuery(urlQuery);
    setSelectedFilters({
      author,
      group,
      book_title,
      search_type: st,
    });

    if (urlQuery.trim()) {
      debouncedSearch(urlQuery, { author, group, book_title, search_type: st });
    } else {
      setAllResults([]);
      setGroupCounts({});
      setActiveGroup('');
      setCurrentPage(1);
    }
  }, [searchParams, defaultSearchType]);

  // Debounced search
  const debouncedSearch = useMemo(() => {
    return debounce(async (newQuery, newFilters) => {
      if (!newQuery.trim()) {
        setError('Please enter a search query.');
        return;
      }
      setLoading(true);
      setError('');
      try {
        const data = await performSearch(newQuery, newFilters, 100);
        if (data.results && Array.isArray(data.results)) {
          setAllResults(data.results);
        } else {
          setAllResults([]);
        }
        setGroupCounts(data.group_counts || {});
        setActiveGroup('');
        setCurrentPage(1);
      } catch (err) {
        console.error('Error performing search:', err);
        setError('Search failed. Please try again.');
      }
      setLoading(false);
    }, 300);
  }, []);

  // Called by the search bar
  const handleSearch = () => {
    const { author, group, book_title, search_type } = selectedFilters;
    setSearchParams({
      query,
      author,
      group,
      book_title,
      search_type,
    });
  };

  // Reset search to defaults
  const handleReset = () => {
    setQuery('');
    setSelectedFilters({
      author: '',
      group: '',
      book_title: '',
      search_type: defaultSearchType, 
    });
    // Optionally clear searchParams
    setSearchParams({});
    setAllResults([]);
    setGroupCounts({});
    setActiveGroup('');
    setCurrentPage(1);
  };

  // local group filter
  const displayedResults = useMemo(() => {
    if (!activeGroup) return allResults;
    return allResults.filter((item) => item.group === activeGroup);
  }, [allResults, activeGroup]);

  // pagination
  const totalPages = Math.ceil(displayedResults.length / resultsPerPage);
  const indexOfLastResult = currentPage * resultsPerPage;
  const indexOfFirstResult = indexOfLastResult - resultsPerPage;
  const currentResults = displayedResults.slice(indexOfFirstResult, indexOfLastResult);

  const displayPage = (page) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const getPaginationRange = () => {
    const range = [];
    const showPages = 5;
    let start = Math.max(1, currentPage - Math.floor(showPages / 2));
    let end = Math.min(totalPages, start + showPages - 1);

    if (end - start + 1 < showPages) {
      start = Math.max(1, end - showPages + 1);
    }

    for (let i = start; i <= end; i++) {
      range.push(i);
    }
    return range;
  };

  // group by book
  const groupedByBook = useMemo(() => {
    const byBook = {};
    currentResults.forEach((res) => {
      const titleKey = res.book_title || 'Untitled';
      if (!byBook[titleKey]) {
        byBook[titleKey] = [];
      }
      byBook[titleKey].push(res);
    });
    return byBook;
  }, [currentResults]);

  return (
    <div className="homepage-container">
      <header className="page-header d-flex align-items-center mb-4">
        <img
          src="/images/sri_ma.jpg"
          alt="Logo"
          className="header-image me-2"
          style={{ width: '100px', height: 'auto' }} // reduce the width to ~50px
        />
        {/* Use the heading prop */}
        <h3 className="mb-0">{heading}</h3>
      </header>

      <SearchBar
        query={query}
        setQuery={setQuery}
        handleSearch={handleSearch}
        loading={loading}
        selectedFilters={selectedFilters}
        setSelectedFilters={setSelectedFilters}
        showSearchTypeControls={showSearchTypeControls}
        onReset={handleReset}
      />

      <Filters
        filters={filters}
        selectedFilters={selectedFilters}
        setSelectedFilters={setSelectedFilters}
      />

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {/* Group Buttons for "Collections" */}
      {Object.keys(groupCounts).length > 0 && (
        <div className="mb-3">
          <strong>Collections Found:</strong>{' '}
          <button
            className={`btn btn-sm ${
              !activeGroup ? 'btn-primary' : 'btn-outline-primary'
            } me-1`}
            onClick={() => setActiveGroup('')}
          >
            All Collections ({allResults.length})
          </button>

          {Object.entries(groupCounts).map(([grp, count]) => {
            const isActive = activeGroup === grp;
            return (
              <button
                key={grp}
                onClick={() => setActiveGroup(grp)}
                className={`btn btn-sm ${
                  isActive ? 'btn-primary' : 'btn-outline-primary'
                } me-1`}
              >
                {grp} ({count})
              </button>
            );
          })}
        </div>
      )}

      <div className="results-container">
        {loading ? (
          <div className="text-center my-4">
            <div className="spinner-border" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : currentResults.length > 0 ? (
          <>
            <div className="results-list">
              {Object.entries(groupedByBook).map(([bookTitle, bookResults]) => {
                if (bookResults.length > 1) {
                  return (
                    <BookAccordion
                      key={bookTitle}
                      bookTitle={bookTitle}
                      results={bookResults}
                      searchTerm={query}
                      searchType={selectedFilters.search_type}
                    />
                  );
                } else {
                  return (
                    <ResultCard
                      key={bookTitle}
                      result={bookResults[0]}
                      searchTerm={query}
                      searchType={selectedFilters.search_type}
                    />
                  );
                }
              })}
            </div>

            {displayedResults.length > resultsPerPage && (
              <nav aria-label="Search results pagination" className="mt-4">
                <ul className="pagination justify-content-center">
                  <li
                    className={`page-item ${
                      currentPage === 1 ? 'disabled' : ''
                    }`}
                  >
                    <button
                      className="page-link"
                      onClick={() => displayPage(currentPage - 1)}
                      disabled={currentPage === 1}
                    >
                      Previous
                    </button>
                  </li>

                  {getPaginationRange().map((page) => (
                    <li
                      key={page}
                      className={`page-item ${
                        currentPage === page ? 'active' : ''
                      }`}
                    >
                      <button
                        className="page-link"
                        onClick={() => displayPage(page)}
                      >
                        {page}
                      </button>
                    </li>
                  ))}

                  <li
                    className={`page-item ${
                      currentPage === totalPages ? 'disabled' : ''
                    }`}
                  >
                    <button
                      className="page-link"
                      onClick={() => displayPage(currentPage + 1)}
                      disabled={currentPage === totalPages}
                    >
                      Next
                    </button>
                  </li>
                </ul>
              </nav>
            )}
          </>
        ) : (
          <p className="text-center my-4">No results found.</p>
        )}
      </div>
    </div>
  );
};

export default SearchPage;
