import React from 'react';
import { useLocation } from 'react-router-dom';
import { Worker, Viewer } from '@react-pdf-viewer/core';
import { defaultLayoutPlugin } from '@react-pdf-viewer/default-layout';
import '@react-pdf-viewer/core/lib/styles/index.css';
import '@react-pdf-viewer/default-layout/lib/styles/index.css';

const PdfViewer = () => {
    const location = useLocation();
    const params = new URLSearchParams(location.search);
    const fileUrl = decodeURIComponent(params.get('file')); // Decode the full URL
    const pageNumber = parseInt(params.get('page'), 10) || 1;

    const defaultLayoutPluginInstance = defaultLayoutPlugin();

    if (!fileUrl) {
        return <p>Error: No PDF file provided.</p>;
    }

    return (
        <div style={{ height: '100vh' }}>
            {/* Explicitly use the correct worker version */}
            <Worker workerUrl="https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js">
                <Viewer
                    fileUrl={fileUrl}
                    plugins={[defaultLayoutPluginInstance]}
                    initialPage={pageNumber - 1} // PDF.js pages are 0-indexed
                />
            </Worker>
        </div>
    );
};

export default PdfViewer;
