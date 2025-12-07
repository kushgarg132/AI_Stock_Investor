import axios from 'axios';

let baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

// Ensure baseUrl doesn't end with a slash for consistent appending
baseUrl = baseUrl.replace(/\/$/, "");

// Append /api/v1 if it's not already there
if (!baseUrl.endsWith('/api/v1')) {
  baseUrl = `${baseUrl}/api/v1`;
}

const API_BASE_URL = baseUrl;

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const endpoints = {
  analyze: (symbol) => `/agents/analyze/${symbol}`,
  scanner: (type = 'bullish') => `/agents/scanner/${type}`,
  stockInfo: (symbol) => `/stock_info/${symbol}`,
  marketIndices: '/market/indices',
  trendingStocks: '/market/trending',
};

export default api;
