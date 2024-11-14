// frontend/src/App.js

import React, { useState, useEffect } from 'react';
import HomePage from './pages/HomePage';
import './App.css'; // Custom styles including dark mode
import 'bootstrap/dist/css/bootstrap.min.css'; // Bootstrap CSS

const App = () => {
    const [darkMode, setDarkMode] = useState(false);

    const toggleDarkMode = () => {
        setDarkMode(!darkMode);
    };

    useEffect(() => {
        if (darkMode) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    }, [darkMode]);

    return (
        <div className="container mt-4">
            <HomePage toggleDarkMode={toggleDarkMode} />
        </div>
    );
};

export default App;
