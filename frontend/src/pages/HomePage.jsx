// frontend/src/pages/HomePage.jsx

import React, { useState, useEffect } from 'react';
import SearchBar from '../components/SearchBar';
import Filters from '../components/Filters';
import ResultCard from '../components/ResultCard';
import { fetchFilters, performSearch } from '../services/api';
import './HomePage.css'; // Ensure to create or update this CSS file

const HomePage = ({ toggleDarkMode }) => {
    const [query, setQuery] = useState('');
    const [filters, setFilters] = useState({ authors: [], groups: [], book_titles: [], book_titles_by_group: {} });
    const [selectedFilters, setSelectedFilters] = useState({ author: '', group: '', book_title: '' });
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
                const sortedAuthors = authorOrder.filter(author => data.authors.includes(author));

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

    const handleSearch = async () => {
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
    };

    const displayPage = (page) => {
        if (page < 1 || page > totalPages) return;
        setCurrentPage(page);
    };

    const safeResults = Array.isArray(results) ? results : [];
    const indexOfLastResult = currentPage * resultsPerPage;
    const indexOfFirstResult = indexOfLastResult - resultsPerPage;
    const currentResults = safeResults.slice(indexOfFirstResult, indexOfLastResult);
    const totalPages = Math.ceil(safeResults.length / resultsPerPage);

    return (
        <div>
            {/* Header Section */}
            <header className="page-header d-flex align-items-center mb-4">
                <img src="/images/sri_ma.jpg" alt="Logo" className="header-image me-2" />  {/* Adjust path */}
                <h1>Search Collected Works of Sri Aurobindo and The Mother</h1>
            </header>

            {/* Search Bar */}
            <SearchBar query={query} setQuery={setQuery} handleSearch={handleSearch} />

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
            <div>
                {currentResults.length > 0 ? (
                    currentResults.map((result, index) => (
                        <ResultCard key={index} result={result} searchTerm={query} />
                    ))
                ) : (
                    <p>No results found.</p>
                )}
            </div>

            {/* Pagination */}
            {safeResults.length > resultsPerPage && (
                <nav aria-label="Search results pagination">
                    <ul className="pagination justify-content-center">
                        <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                            <button className="page-link" onClick={() => displayPage(currentPage - 1)}>
                                Previous
                            </button>
                        </li>
                        <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
                            <button className="page-link" onClick={() => displayPage(currentPage + 1)}>
                                Next
                            </button>
                        </li>
                    </ul>
                </nav>
            )}
        </div>
    );
};

export default HomePage;
