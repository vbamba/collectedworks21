// frontend/src/services/api.js
import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://127.0.0.1:5001';

/**
 * Fetches filter options from the backend.
 * @returns {Promise<Object>} Filters including authors, groups, and book titles.
 */
export const fetchFilters = async () => {
    try {
        const response = await axios.get(`${API_BASE_URL}/filters`);
        return response.data;
    } catch (error) {
        console.error("Error fetching filters:", error);
        throw error;
    }
};

/**
 * Performs a search query with optional filters.
 * @param {string} query - The search query.
 * @param {Object} filters - Filters including author, group, and book_title.
 * @param {number} top_k - Number of top results to fetch.
 * @returns {Promise<Object>} Search results.
 */
export const performSearch = async (query, filters, top_k = 100) => {
    try {
        const params = {
            query,
            author: filters.author,
            group: filters.group,
            book_title: filters.book_title,
            search_type: filters.search_type,
            top_k: filters.top_k || 100,
        };        
        const response = await axios.get(`${API_BASE_URL}/search`, { params });
        return response.data;
    } catch (error) {
        console.error("Error performing search:", error);
        throw error;
    }
};


