// frontend/src/components/ResultCard.jsx
import React from 'react';

const ResultCard = ({ result, searchTerm }) => {
    const { book_title, chapter_name, snippet, pdf_url, page_number } = result;

    // Construct PDF.js Viewer URL
    const pdfViewerUrl = 'http://127.0.0.1:5000/pdfjs/web/viewer.html'; // Adjust if needed
    const pdfFileUrl = encodeURIComponent(pdf_url);
    const encodedSearchTerm = encodeURIComponent(searchTerm);
    const pdfUrlWithHighlight = `${pdfViewerUrl}?file=${pdfFileUrl}#page=${page_number}&search=${encodedSearchTerm}`;

    return (
        <div className="card result-card">
            <div className="card-body">
                <h5 className="card-title">
                    <a href={pdfUrlWithHighlight} target="_blank" rel="noopener noreferrer" title={book_title}>
                        {book_title}
                    </a>
                </h5>
                {chapter_name && (
                    <h6 className="card-subtitle mb-2 text-muted">{chapter_name}</h6>
                )}
                <p
                    className="card-text result-snippet"
                    dangerouslySetInnerHTML={{ __html: snippet.replace(/\n/g, '<br>') }}
                ></p>
            </div>
        </div>
    );
};

export default ResultCard;
