// frontend/src/components/ResultCard.jsx

import React from 'react';
import PropTypes from 'prop-types';
import DOMPurify from 'dompurify';

const ResultCard = ({ result, searchTerm }) => {
    const { book_title, page_number, pdf_url, snippet, distance } = result;

    // Construct the PDF URL with the correct page
    const pdfUrlWithPage = `${encodeURI(pdf_url.split('#page=')[0])}#page=${page_number}`;

    // Sanitize the snippet and replace \n with <br/>
    const sanitizedSnippet = DOMPurify.sanitize(
        (snippet || 'No snippet available.')
            .replace(/\n/g, '<br/>')
            .replace(new RegExp(`(${searchTerm})`, 'gi'), '<mark>$1</mark>')
    );

    return (
        <div className="card mb-3">
            <div className="card-body">
                <h5 className="card-title">{book_title || 'Untitled'}</h5>
                
                <p className="card-text" dangerouslySetInnerHTML={{ __html: sanitizedSnippet }}></p>
                <div className="d-flex justify-content-between align-items-center">
                    {/* Replace PdfViewer with a simple hyperlink */}
                    <a href={pdfUrlWithPage} target="_blank" rel="noopener noreferrer">
                        Open PDF
                    </a>
                </div>
                <small className="text-muted">Distance: {distance !== undefined ? distance.toFixed(2) : 'N/A'}</small>
            </div>
        </div>
    );
};

ResultCard.propTypes = {
    result: PropTypes.shape({
        book_title: PropTypes.string,
        page_number: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        pdf_url: PropTypes.string,
        snippet: PropTypes.string,
        distance: PropTypes.number
    }).isRequired,
    searchTerm: PropTypes.string.isRequired
};

export default ResultCard;
