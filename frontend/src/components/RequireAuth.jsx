import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const RequireAuth = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--paper)]">
        <p className="field-label" role="status">
          Retrieving note…
        </p>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return children;
};

export default RequireAuth;
