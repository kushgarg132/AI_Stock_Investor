import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ScannerPage from './pages/ScannerPage';
import GoalsPage from './pages/GoalsPage';
import Watchlist from './pages/Watchlist';
import Portfolio from './pages/Portfolio';
import Settings from './pages/Settings';

const App = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/goals" element={<GoalsPage />} />
      <Route path="/watchlist" element={<Watchlist />} />
      <Route path="/portfolio" element={<Portfolio />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>
  );
};

export default App;
