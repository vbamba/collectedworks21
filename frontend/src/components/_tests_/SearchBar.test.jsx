// frontend/src/components/__tests__/SearchBar.test.jsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SearchBar from '../SearchBar';

test('renders search bar and handles input', () => {
    const handleSearch = jest.fn();
    const setQuery = jest.fn();

    render(<SearchBar query="" setQuery={setQuery} handleSearch={handleSearch} />);

    const inputElement = screen.getByPlaceholderText(/enter your search query/i);
    expect(inputElement).toBeInTheDocument();

    fireEvent.change(inputElement, { target: { value: 'test query' } });
    expect(setQuery).toHaveBeenCalledWith('test query');

    fireEvent.keyPress(inputElement, { key: 'Enter', code: 'Enter', charCode: 13 });
    expect(handleSearch).toHaveBeenCalled();
});
