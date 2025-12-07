import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001/api/v1';

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
