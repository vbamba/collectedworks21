// frontend/src/pages/HomePage.jsx
import React, { useState, useEffect } from 'react';
import SearchBar from '../components/SearchBar';
import Filters from '../components/Filters';
import ResultCard from '../components/ResultCard';
import { fetchFilters, performSearch } from '../services/api';

const HomePage = () => {
    const [query, setQuery] = useState('');
    const [filters, setFilters] = useState({ authors: [], groups: [], book_titles: [] });
    const [selectedFilters, setSelectedFilters] = useState({ author: '', group: '', book_title: '', top_k: 100 });
    const [results, setResults] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const resultsPerPage = 5;
    const [darkMode, setDarkMode] = useState(false);

    useEffect(() => {
        // Fetch filters on component mount
        fetchFilters()
            .then(response => {
                setFilters(response.data);
            })
            .catch(error => {
                console.error("Error fetching filters:", error);
            });
    }, []);

    const handleSearch = () => {
        performSearch(query, selectedFilters)
            .then(response => {
                setResults(response.data.results);
                setCurrentPage(1);
            })
            .catch(error => {
                console.error("Error performing search:", error);
            });
    };

    const displayPage = (page) => {
        setCurrentPage(page);
    };

    // Pagination logic
    const indexOfLastResult = currentPage * resultsPerPage;
    const indexOfFirstResult = indexOfLastResult - resultsPerPage;
    const currentResults = results.slice(indexOfFirstResult, indexOfLastResult);
    const totalPages = Math.ceil(results.length / resultsPerPage);

    const toggleDarkMode = () => {
        setDarkMode(!darkMode);
    };

    return (
        <div className={darkMode ? 'dark-mode' : ''}>
            {/* Search Bar */}
            <SearchBar query={query} setQuery={setQuery} handleSearch={handleSearch} />

            {/* Filters */}
            <Filters filters={filters} selectedFilters={selectedFilters} setSelectedFilters={setSelectedFilters} />

            {/* Search Button and Dark Mode Toggle */}
            <div className="row mb-3">
                <div className="col-12">
                    <button onClick={handleSearch} className="btn btn-primary">Search</button>
                    <button onClick={toggleDarkMode} className="btn btn-secondary float-end">Toggle Dark Mode</button>
                </div>
            </div>

            {/* Results */}
            <div>
                {currentResults.map((result, index) => (
                    <ResultCard key={index} result={result} searchTerm={query} />
                ))}
            </div>

            {/* Pagination */}
            {results.length > resultsPerPage && (
                <nav aria-label="Search results pagination">
                    <ul className="pagination justify-content-center">
                        <li className={`page-item ${currentPage === 1 ? 'disabled' : ''}`}>
                            <button className="page-link" onClick={() => displayPage(currentPage - 1)}>Previous</button>
                        </li>
                        <li className={`page-item ${currentPage === totalPages ? 'disabled' : ''}`}>
                            <button className="page-link" onClick={() => displayPage(currentPage + 1)}>Next</button>
                        </li>
                    </ul>
                </nav>
            )}
        </div>
    );
};

export default HomePage;
