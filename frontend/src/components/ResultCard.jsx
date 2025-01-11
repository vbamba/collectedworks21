import React from 'react';
import PropTypes from 'prop-types';
import DOMPurify from 'dompurify';

const ResultCard = ({ result, searchTerm, maxLines = 10 }) => {
    const { book_title, page_number, pdf_url, snippet, distance } = result;

    // Base URL for the backend
    const BACKEND_BASE_URL = process.env.REACT_APP_BACKEND_PDF_URL || '';
    const pdfUrlWithPage = `${BACKEND_BASE_URL}${encodeURI(pdf_url.split('#page=')[0])}#page=${page_number}`;

    // Function to limit the snippet to a certain number of lines
    const truncateSnippet = (htmlSnippet, maxLines) => {
        const lines = htmlSnippet.split('<br/>');
        if (lines.length > maxLines) {
            return lines.slice(0, maxLines).join('<br/>') + '<br/>...';
        }
        return htmlSnippet;
    };

    // Sanitize and highlight the snippet
    const sanitizedSnippet = DOMPurify.sanitize(
        truncateSnippet(
            (snippet || 'No snippet available.')
                .replace(/\n/g, '<br/>')
                .replace(new RegExp(`(${searchTerm})`, 'gi'), '<mark>$1</mark>'),
            maxLines
        )
    );

    return (
        <div className="card mb-3">
            <div className="card-body">
                <h5 className="card-title">
                    <a href={pdfUrlWithPage} target="_blank" rel="noopener noreferrer" className="text-decoration-none">
                        {book_title || 'Untitled'}
                    </a>
                </h5>
                <p className="card-text" dangerouslySetInnerHTML={{ __html: sanitizedSnippet }}></p>
                <div className="d-flex justify-content-between align-items-center">
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
    searchTerm: PropTypes.string.isRequired,
    maxLines: PropTypes.number
};

export default ResultCard;
