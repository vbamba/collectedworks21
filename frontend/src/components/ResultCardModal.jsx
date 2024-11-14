// frontend/src/components/ResultCard.jsx

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import Modal from 'react-modal';
import PdfViewer from './PdfViewer';

// Bind modal to the app element for accessibility
Modal.setAppElement('#root');

const ResultCard = ({ result }) => {
    const { author, book_title, chapter_name, page_number, pdf_url, snippet, distance, priority } = result;
    const [modalIsOpen, setModalIsOpen] = useState(false);

    const openModal = () => {
        setModalIsOpen(true);
    };

    const closeModal = () => {
        setModalIsOpen(false);
    };

    return (
        <div className="card mb-3">
            <div className="card-body">
                <h5 className="card-title">{book_title || 'Untitled'}</h5>
                <p className="card-text" dangerouslySetInnerHTML={{ __html: snippet || 'No snippet available.' }}></p>
                <div className="d-flex justify-content-between align-items-center">
                    <button onClick={openModal} className="btn btn-link card-link">
                        View PDF
                    </button>
                    <span className="badge bg-secondary">Priority: {priority || 'N/A'}</span>
                </div>
                <small className="text-muted">Distance: {distance !== undefined ? distance.toFixed(2) : 'N/A'}</small>

                {/* Modal for PDF Viewer */}
                <Modal
                    isOpen={modalIsOpen}
                    onRequestClose={closeModal}
                    contentLabel="PDF Viewer"
                    style={{
                        content: {
                            top: '50%',
                            left: '50%',
                            right: 'auto',
                            bottom: 'auto',
                            marginRight: '-50%',
                            transform: 'translate(-50%, -50%)',
                            maxHeight: '90vh',
                            overflow: 'auto'
                        }
                    }}
                >
                    <button onClick={closeModal} className="btn btn-danger mb-3">Close</button>
                    <PdfViewer pdfUrl={pdf_url} initialPage={page_number} />
                </Modal>
            </div>
        </div>
    );
};

ResultCard.propTypes = {
    result: PropTypes.shape({
        author: PropTypes.string,
        book_title: PropTypes.string,
        chapter_name: PropTypes.string,
        page_number: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        pdf_url: PropTypes.string,
        snippet: PropTypes.string,
        distance: PropTypes.number,
        priority: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
    }).isRequired
};

export default ResultCardModal;
