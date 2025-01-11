// frontend/src/pages/HomePage.jsx

import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { debounce } from 'lodash';
import SearchBar from '../components/SearchBar';
import Filters from '../components/Filters';
import ResultCard from '../components/ResultCard';
import { fetchFilters, performSearch } from '../services/api';
import './HomePage.css';

const HomePage = () => {
  // 1) Use React Router's search params hook
  const [searchParams, setSearchParams] = useSearchParams();

  // 2) States
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState({
    authors: [],
    groups: [],
    book_titles: [],
    book_titles_by_group: {},
  });
  const [selectedFilters, setSelectedFilters] = useState({
    author: '',
    group: '',
    book_title: '',
    search_type: 'all',
  });
  const [results, setResults] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const resultsPerPage = 10;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Derived
  const safeResults = Array.isArray(results) ? results : [];
  const totalPages = Math.ceil(safeResults.length / resultsPerPage);
  const indexOfLastResult = currentPage * resultsPerPage;
  const indexOfFirstResult = indexOfLastResult - resultsPerPage;
  const currentResults = safeResults.slice(indexOfFirstResult, indexOfLastResult);

  // --------------------------------------------
  // Fetch filters on mount
  // --------------------------------------------
  useEffect(() => {
    const getFilters = async () => {
      try {
        const data = await fetchFilters();
        // Sort authors
        const authorOrder = ['Sri Aurobindo', 'The Mother', 'Disciples'];
        const sortedAuthors = authorOrder.filter((author) =>
          data.authors.includes(author)
        );

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

  // --------------------------------------------
  // On first mount or whenever URL changes,
  // parse query params and update state.
  // --------------------------------------------
  useEffect(() => {
    const urlQuery = searchParams.get('query') || '';
    const author = searchParams.get('author') || '';
    const group = searchParams.get('group') || '';
    const book_title = searchParams.get('book_title') || '';
    const search_type = searchParams.get('search_type') || 'all';

    setQuery(urlQuery);
    setSelectedFilters({ author, group, book_title, search_type });
    
    // If there's a query in the URL, automatically search
    if (urlQuery.trim()) {
      debouncedSearch(urlQuery, { author, group, book_title, search_type });
    } else {
      setResults([]);
    }
  }, [searchParams]);

  // --------------------------------------------
  // Debounced search function
  // (You already have something similar)
  // --------------------------------------------
  const debouncedSearch = debounce(async (newQuery, newFilters) => {
    if (!newQuery.trim()) {
      setError('Please enter a search query.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await performSearch(newQuery, newFilters, 100);
      setResults(Array.isArray(data.results) ? data.results : []);
      setCurrentPage(1);
    } catch (err) {
      console.error('Error performing search:', err);
      setError('Search failed. Please try again.');
    }
    setLoading(false);
  }, 300);

  // --------------------------------------------
  // Called by SearchBar when user clicks "Search"
  // --------------------------------------------
  const handleSearch = () => {
    // 1) Put new params in URL
    const { author, group, book_title, search_type } = selectedFilters;
    setSearchParams({
      query,
      author,
      group,
      book_title,
      search_type,
    });
    // 2) The effect above will see these new params, call search
  };

  // Pagination helpers
  const displayPage = (page) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
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

  return (
    <div className="homepage-container">
      {/* Header */}
      <header className="page-header d-flex align-items-center mb-4">
        <img
          src="/images/sri_ma.jpg"
          alt="Logo"
          className="header-image me-2"
        />
        <h1>Search Collected Works of Sri Aurobindo and The Mother</h1>
      </header>

      {/* Search Bar */}
      <SearchBar
        query={query}
        setQuery={setQuery}
        handleSearch={handleSearch}
        loading={loading}
        selectedFilters={selectedFilters}
        setSelectedFilters={setSelectedFilters}
      />

      {/* Filters */}
      <Filters
        filters={filters}
        selectedFilters={selectedFilters}
        setSelectedFilters={setSelectedFilters}
      />

      {/* Error Message */}
      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {/* Results */}
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
              {currentResults.map((result, index) => (
                <ResultCard
                  key={`${result.id || index}`}
                  result={result}
                  searchTerm={query}
                />
              ))}
            </div>
            {/* Pagination */}
            {safeResults.length > resultsPerPage && (
              <nav
                aria-label="Search results pagination"
                className="mt-4"
              >
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

export default HomePage;
