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

const TOKEN_STORAGE_KEY = 'asi_token';

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (token && config.url !== '/auth/google') {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      if (window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
    }
    return Promise.reject(error);
  }
);

export const AUTH_TOKEN_STORAGE_KEY = TOKEN_STORAGE_KEY;

export const endpoints = {
  analyze: (symbol) => `/agents/analyze/${symbol}`,
  scanner: '/scanner/bullish',
  stockInfo: (symbol) => `/stock_info/${symbol}`,
  marketIndices: '/market/indices',
  trendingStocks: '/market/trending',
  watchlist: {
    get: (userId) => `/watchlist/${userId}`,
    add: (userId, symbol) => `/watchlist/${userId}/add?symbol=${symbol}`,
    remove: (userId, symbol) => `/watchlist/${userId}/remove/${symbol}`,
    details: (userId) => `/watchlist/${userId}/details`,
  },
  globalIndices: '/market/global',
  marketNews: '/news/market',
  trading: {
    start: '/trading/start',
    stop: '/trading/stop',
    positions: '/trading/positions',
    fills: '/trading/fills',
    equity: '/trading/equity',
    instruments: (q) => `/trading/instruments?q=${encodeURIComponent(q)}`,
  },
  settings: {
    omnirouteModels: '/settings/omniroute-models',
    omnirouteModel: '/settings/omniroute-model',
  },
  auth: {
    google: '/auth/google',
    logout: '/auth/logout',
    me: '/auth/me',
  },
};

export default api;
