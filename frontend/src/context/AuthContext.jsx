import React, { createContext, useContext, useEffect, useState } from 'react';
import api, { endpoints, AUTH_TOKEN_STORAGE_KEY } from '../utils/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
            if (!token) {
                if (!cancelled) setLoading(false);
                return;
            }
            try {
                const res = await api.get(endpoints.auth.me);
                if (!cancelled) setUser(res.data);
            } catch {
                if (!cancelled) {
                    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
                    setUser(null);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const login = async (idToken) => {
        const res = await api.post(endpoints.auth.google, { id_token: idToken });
        localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, res.data.token);
        setUser(res.data.user);
    };

    const logout = () => {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, loading, login, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

// Co-locating the hook with its Provider is the standard React context
// pattern; this rule only affects Fast Refresh granularity, not correctness.
// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error('useAuth must be used within AuthProvider');
    return ctx;
};
