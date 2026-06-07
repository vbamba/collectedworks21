// frontend/src/components/__tests__/SearchBar.test.jsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SearchBar from '../SearchBar';

test('renders search bar and handles input', () => {
    const handleSearch = vi.fn();
    const setQuery = vi.fn();

    // CHANGED: supply the selectedFilters/setSelectedFilters props the
    // component now requires (it reads selectedFilters.search_type). The
    // original test predates that prop and crashed on undefined.
    render(
        <SearchBar
            query=""
            setQuery={setQuery}
            handleSearch={handleSearch}
            selectedFilters={{ search_type: 'all' }}
            setSelectedFilters={vi.fn()}
        />
    );

    const inputElement = screen.getByPlaceholderText(/enter your search query/i);
    expect(inputElement).toBeInTheDocument();

    fireEvent.change(inputElement, { target: { value: 'test query' } });
    expect(setQuery).toHaveBeenCalledWith('test query');

    fireEvent.keyPress(inputElement, { key: 'Enter', code: 'Enter', charCode: 13 });
    expect(handleSearch).toHaveBeenCalled();
});
