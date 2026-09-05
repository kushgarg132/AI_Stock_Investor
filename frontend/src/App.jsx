import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ScannerPage from './pages/ScannerPage';
import Watchlist from './pages/Watchlist';
import Portfolio from './pages/Portfolio';
import Trading from './pages/Trading';
import Settings from './pages/Settings';

import SystemArchitecturePage from './pages/SystemArchitecturePage';

const App = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/scanner" element={<ScannerPage />} />
      <Route path="/trading" element={<Trading />} />
      <Route path="/watchlist" element={<Watchlist />} />
      <Route path="/portfolio" element={<Portfolio />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/system" element={<SystemArchitecturePage />} />
    </Routes>
  );
};

export default App;
