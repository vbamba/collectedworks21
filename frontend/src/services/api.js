// frontend/src/services/api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:5001';

export const fetchFilters = () => {
    return axios.get(`${API_BASE_URL}/filters`);
};

export const performSearch = (query, filters) => {
    const params = {
        query,
        author: filters.author,
        group: filters.group,
        book_title: filters.book_title,
        top_k: filters.top_k || 100,
    };
    return axios.get(`${API_BASE_URL}/search`, { params });
};
