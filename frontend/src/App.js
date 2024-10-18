// frontend/src/App.js
import React from 'react';
import HomePage from './pages/HomePage';
import './App.css'; // Custom styles including dark mode

const App = () => {
    return (
        <div className="container mt-4">
            <HomePage />
        </div>
    );
};

export default App;
