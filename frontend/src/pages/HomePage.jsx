// frontend/src/pages/HomePage.jsx

import React, { useState, useEffect } from 'react';
import { debounce } from 'lodash';
import SearchBar from '../components/SearchBar';
import Filters from '../components/Filters';
import ResultCard from '../components/ResultCard';
import { fetchFilters, performSearch } from '../services/api';
import './HomePage.css';

const HomePage = ({ toggleDarkMode }) => {
    const [query, setQuery] = useState('');
    const [filters, setFilters] = useState({ 
        authors: [], 
        groups: [], 
        book_titles: [], 
        book_titles_by_group: {} 
    });
    const [selectedFilters, setSelectedFilters] = useState({ 
        author: '', 
        group: '', 
        book_title: '',
        search_type: 'all' 
    });
    const [results, setResults] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const resultsPerPage = 10;
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        const getFilters = async () => {
            try {
                const data = await fetchFilters();
                // Define the desired author order
                const authorOrder = ["Sri Aurobindo", "The Mother", "Disciples"];
                const sortedAuthors = authorOrder.filter(author => 
                    data.authors.includes(author)
                );

                setFilters({
                    ...data,
                    authors: sortedAuthors
                });
            } catch (err) {
                console.error("Error fetching filters:", err);
                setError('Failed to load filters.');
            }
        };
        getFilters();
    }, []);

    const handleSearch = debounce(async () => {
        if (!query.trim()) {
            setError('Please enter a search query.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            const searchFilters = {
                author: selectedFilters.author,
                group: selectedFilters.group,
                book_title: selectedFilters.book_title,
                search_type: selectedFilters.search_type
            };
            const data = await performSearch(query, searchFilters, 100);
            setResults(Array.isArray(data.results) ? data.results : []);
            setCurrentPage(1);
        } catch (err) {
            console.error("Error performing search:", err);
            setError('Search failed. Please try again.');
        }
        setLoading(false);
    }, 300);

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

    const safeResults = Array.isArray(results) ? results : [];
    const indexOfLastResult = currentPage * resultsPerPage;
    const indexOfFirstResult = indexOfLastResult - resultsPerPage;
    const currentResults = safeResults.slice(indexOfFirstResult, indexOfLastResult);
    const totalPages = Math.ceil(safeResults.length / resultsPerPage);

    return (
        <div className="homepage-container">
            {/* Header Section */}
            <header className="page-header d-flex align-items-center mb-4">
                <img src="/images/sri_ma.jpg" alt="Logo" className="header-image me-2" />
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

            {/* Results Section */}
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
                            <nav aria-label="Search results pagination" className="mt-4">
                                <ul className="pagination justify-content-center">
                                    <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                                        <button 
                                            className="page-link" 
                                            onClick={() => displayPage(currentPage - 1)}
                                            disabled={currentPage === 1}
                                        >
                                            Previous
                                        </button>
                                    </li>
                                    
                                    {getPaginationRange().map(page => (
                                        <li 
                                            key={page} 
                                            className={`page-item ${currentPage === page ? 'active' : ''}`}
                                        >
                                            <button 
                                                className="page-link" 
                                                onClick={() => displayPage(page)}
                                            >
                                                {page}
                                            </button>
                                        </li>
                                    ))}
                                    
                                    <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
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
