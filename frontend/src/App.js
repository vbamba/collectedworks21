import React from 'react';
import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SemanticPage from './pages/SemanticPage';
import TextSearchPage  from './pages/TextSearchPage';  // ← your new page
import ChapterPage    from './pages/ChapterPage';
import PdfViewer from './components/PdfViewer'; // Import PdfViewer component
import './App.css';
import 'bootstrap/dist/css/bootstrap.min.css';

const App = () => {
    return (
        <div className="container mt-4">
            <Routes>
                <Route path="/" element={<TextSearchPage />} />                
                <Route path="/question" element={<SemanticPage />} />  
                <Route path="/chat" element={<SemanticPage />} />                  
                <Route path="/searchtext"     element={<TextSearchPage />} />  
                <Route path="/ai"     element={<HomePage />} />                  
                <Route path="/chapter"  element={<ChapterPage />} />
                {/* CHANGED: slug-based chapter URLs were previously served only
                    by Flask's chapter.html template. Route them through the SPA
                    ChapterPage too so we have a single chapter renderer, and so
                    /read/... URLs (which nginx falls back to index.html for) no
                    longer hit the SPA shell with no matching route. */}
                <Route path="/read/:collection/:bookSlug/:slug" element={<ChapterPage />} />
                <Route path="/viewer" element={<PdfViewer />} /> {/* Add the route for PdfViewer */}
            </Routes>
        </div>
    );
};

export default App;
