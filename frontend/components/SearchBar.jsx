// frontend/src/components/SearchBar.jsx
import React from 'react';

const SearchBar = ({ query, setQuery, handleSearch }) => {
    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    return (
        <input
            type="text"
            className="form-control"
            placeholder="Enter your search query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
        />
    );
};

export default SearchBar;
