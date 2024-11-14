// frontend/src/components/PdfViewer.jsx

import React from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import './PdfViewer.css';

// Set the workerSrc to point to the correct worker script
pdfjs.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL}/pdf.worker.min.js`;

const PdfViewer = ({ url, searchTerm }) => {
    const pageNumber = url.split('#page=')[1] ? parseInt(url.split('#page=')[1], 10) : 1;

    return (
        <div className="pdf-container">
            <Document
                file={url}
                onLoadError={error => console.error('Error loading PDF:', error)}
            >
                <Page pageNumber={pageNumber} />
            </Document>
        </div>
    );
};

export default PdfViewer;
