// frontend/src/components/BookAccordion.jsx

import React, { useState } from 'react';
import ResultCard from './ResultCard';

/**
 * Renders a collapsible "accordion" for a book that has multiple matches.
 * 
 * Props:
 *  - bookTitle (string): the book title
 *  - results (array): array of result objects
 *  - searchTerm (string)
 *  - searchType (string)
 */
const BookAccordion = ({ bookTitle, results, searchTerm, searchType }) => {
  // State to track whether this accordion is open or closed
  const [isOpen, setIsOpen] = useState(true);

  const toggleAccordion = () => {
    setIsOpen(!isOpen);
  };

  return (
    <div className="mb-3">
      {/* Header row */}
      <div 
        onClick={toggleAccordion} 
        style={{ cursor: 'pointer', fontWeight: 'bold' }}
        className="bg-light p-2"
      >
        {bookTitle} ({results.length} matches)
        <span style={{ float: 'right' }}>
          {isOpen ? '[-]' : '[+]'}
        </span>
      </div>

      {/* Body (ResultCards) */}
      {isOpen && (
        <div className="mt-2 ps-3">
          {results.map((res, index) => (
            <ResultCard
              key={index}
              result={res}
              searchTerm={searchTerm}
              searchType={searchType}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default BookAccordion;
