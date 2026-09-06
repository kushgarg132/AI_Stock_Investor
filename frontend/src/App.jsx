import React, { useEffect } from 'react';
import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Suggestions from './pages/Suggestions';
import ScannerPage from './pages/ScannerPage';
import Watchlist from './pages/Watchlist';
import Portfolio from './pages/Portfolio';
import Trading from './pages/Trading';
import Settings from './pages/Settings';
import Login from './pages/Login';
import SystemArchitecturePage from './pages/SystemArchitecturePage';
import RequireAuth from './components/RequireAuth';
import Layout from './components/Layout';
import { Sheet, Empty } from './components/doc/Doc';
import { useAuth } from './context/AuthContext';
import { stream } from './lib/ws';

const NotFound = () => (
  <Layout>
    <Sheet title="Not found">
      <Empty
        title="No such section of the note"
        detail="The address does not match any part of this statement."
        action={
          <Link to="/" className="field-label text-[var(--stamp)] hover:underline">
            Back to the statement
          </Link>
        }
      />
    </Sheet>
  </Layout>
);

const App = () => {
  const { user } = useAuth();

  // One socket for the whole session, opened once signed in and closed on the
  // way out so a logged-out tab never holds an authenticated connection.
  useEffect(() => {
    if (user) {
      stream.connect();
      return () => stream.disconnect();
    }
    return undefined;
  }, [user]);

  const gated = (element) => <RequireAuth>{element}</RequireAuth>;

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={gated(<Dashboard />)} />
      <Route path="/suggestions" element={gated(<Suggestions />)} />
      <Route path="/scanner" element={gated(<ScannerPage />)} />
      <Route path="/trading" element={gated(<Trading />)} />
      <Route path="/watchlist" element={gated(<Watchlist />)} />
      <Route path="/portfolio" element={gated(<Portfolio />)} />
      <Route path="/settings" element={gated(<Settings />)} />
      <Route path="/system" element={gated(<SystemArchitecturePage />)} />
      <Route path="*" element={gated(<NotFound />)} />
    </Routes>
  );
};

export default App;
