import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/useTheme';
import { formatNoteDate } from '../utils/formatters';

/** The cover sheet: the note's head, unfilled, waiting to be issued to someone. */
const Login = () => {
  const { login } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const [error, setError] = useState('');

  const onSuccess = async (credentialResponse) => {
    try {
      await login(credentialResponse.credential);
      navigate('/');
    } catch {
      setError('Sign-in failed. Try again.');
    }
  };

  return (
    <div className="min-h-screen bg-[var(--paper-sunk)] flex items-center justify-center p-4">
      <div className="w-full max-w-sm sheet">
        <div className="px-6 py-5 border-b border-[var(--rule-strong)] text-center">
          <h1 className="font-[family-name:var(--font-narrow)] font-bold uppercase tracking-[0.2em] text-sm">
            Contract Note
          </h1>
          <p className="doc-meta mt-1.5">AI Stock Investor · NSE · {formatNoteDate()}</p>
        </div>

        <div className="px-6 py-8">
          <dl className="space-y-3 mb-8">
            {[
              ['Issued to', '—'],
              ['Account', '—'],
              ['Status', 'Unissued'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-4">
                <dt className="field-label">{label}</dt>
                <dd className="flex-1 border-b border-dotted border-[var(--rule)] mx-2" aria-hidden="true" />
                <dd className="figure-md text-sm text-[var(--ink-faint)]">{value}</dd>
              </div>
            ))}
          </dl>

          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={onSuccess}
              onError={() => setError('Sign-in failed. Try again.')}
              theme={theme === 'dark' ? 'filled_black' : 'outline'}
              shape="square"
              width="280"
            />
          </div>

          {error && (
            <p
              role="alert"
              className="mt-4 text-sm text-center text-[var(--loss)] border border-[var(--loss)] bg-[var(--loss-wash)] px-3 py-2"
            >
              {error}
            </p>
          )}
        </div>

        <p className="px-6 py-3 border-t border-[var(--rule)] doc-meta text-center normal-case">
          Paper trading only. No real orders are placed.
        </p>
      </div>
    </div>
  );
};

export default Login;
