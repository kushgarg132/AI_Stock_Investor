import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import ScannerPage from './pages/ScannerPage';
import Watchlist from './pages/Watchlist';
import Portfolio from './pages/Portfolio';
import Trading from './pages/Trading';
import Settings from './pages/Settings';
import Login from './pages/Login';
import RequireAuth from './components/RequireAuth';

import SystemArchitecturePage from './pages/SystemArchitecturePage';

const App = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
      <Route path="/scanner" element={<RequireAuth><ScannerPage /></RequireAuth>} />
      <Route path="/trading" element={<RequireAuth><Trading /></RequireAuth>} />
      <Route path="/watchlist" element={<RequireAuth><Watchlist /></RequireAuth>} />
      <Route path="/portfolio" element={<RequireAuth><Portfolio /></RequireAuth>} />
      <Route path="/settings" element={<RequireAuth><Settings /></RequireAuth>} />
      <Route path="/system" element={<RequireAuth><SystemArchitecturePage /></RequireAuth>} />
    </Routes>
  );
};

export default App;
