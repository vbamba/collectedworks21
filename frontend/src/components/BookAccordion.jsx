// frontend/src/components/BookAccordion.jsx
import React, { useState } from 'react';
import ResultCard from './ResultCard';
import TextResultCard from './TextResultCard';

/**
 * An accordion that groups results by book.
 *
 * Props:
 *  - bookTitle: string title of the book
 *  - results: array of result objects
 *  - searchTerm: the current query string
 *  - searchType: 'exact' | 'all_words' | 'semantic'
 *  - isTextSearch: boolean; if true, render TextResultCard
 */
const BookAccordion = ({
  bookTitle,
  results,
  searchTerm,
  searchType,
  isTextSearch = false,
}) => {
  // Hooks must be at top level
  const canToggle = results.length > 1;
  const [isOpen, setIsOpen] = useState(true);
  const toggleAccordion = () => {
    if (!canToggle) return;
    setIsOpen(prev => !prev);
  };

  // Special case: single text-search result—render combined card without header
  if (isTextSearch && results.length === 1) {
    return (
      <TextResultCard
        result={results[0]}
        bookTitle={bookTitle}
        singleResult={true}
        query={searchTerm}
        searchType={searchType}
      />
    );
  }

  const anchorId = `book-${bookTitle.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-_]/g, '')}`;

  return (
    <div className="mb-3">
      {/* Accordion header */}
      <div
        id={anchorId}
        onClick={toggleAccordion}
        style={{ cursor: canToggle ? 'pointer' : 'default', fontWeight: 'bold' }}
        className="bg-light p-2"
      >
        {bookTitle} ({results.length} matches)
        {canToggle && <span style={{ float: 'right' }}>{isOpen ? '[-]' : '[+]'}</span>}
      </div>

      {/* Accordion body */}
      {isOpen && (
        <div className="mt-2 ps-3">
          {results.map((res, i) => (
            isTextSearch ? (
              <TextResultCard
                key={res.section_filename || i}
                result={res}
                bookTitle={bookTitle}
                singleResult={false}
                query={searchTerm}
                searchType={searchType}
              />
            ) : (
              <ResultCard
                key={res.section_filename || i}
                result={res}
                searchTerm={searchTerm}
                searchType={searchType}
              />
            )
          ))}
        </div>
      )}
    </div>
  );
};

export default BookAccordion;
