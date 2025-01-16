import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SemanticPage from './pages/SemanticPage';
import PdfViewer from './components/PdfViewer'; // Import PdfViewer component
import './App.css';
import 'bootstrap/dist/css/bootstrap.min.css';

const App = () => {
    return (
        <div className="container mt-4">
            <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/question" element={<SemanticPage />} />                
                <Route path="/viewer" element={<PdfViewer />} /> {/* Add the route for PdfViewer */}
            </Routes>
        </div>
    );
};

export default App;
