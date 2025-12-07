import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { UserCog, Key, Save, Eye, EyeOff, CheckCircle, AlertCircle } from 'lucide-react';

const Settings = () => {
    const [apiKey, setApiKey] = useState('');
    const [showKey, setShowKey] = useState(false);
    const [status, setStatus] = useState({ loading: false, message: '', type: '' });
    const [keyStatus, setKeyStatus] = useState({ isSet: false, maskedKey: '' });

    useEffect(() => {
        fetchKeyStatus();
    }, []);

    const fetchKeyStatus = async () => {
        try {
            const response = await fetch('http://localhost:8001/api/v1/settings/gemini-keys');
            if (response.ok) {
                const data = await response.json();
                setKeyStatus({ isSet: data.is_set, maskedKey: data.masked_key || '' });
            }
        } catch (error) {
            console.error('Failed to fetch key status:', error);
        }
    };

    const handleSave = async (e) => {
        e.preventDefault();
        if (!apiKey.trim()) {
            setStatus({ message: 'Please enter a valid API key', type: 'error' });
            return;
        }

        setStatus({ loading: true, message: '', type: '' });
        try {
            const response = await fetch('http://localhost:8001/api/v1/settings/gemini-keys', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ gemini_api_key: apiKey }),
            });

            if (response.ok) {
                setStatus({ message: 'API Key saved successfully!', type: 'success' });
                setApiKey('');
                fetchKeyStatus();
            } else {
                setStatus({ message: 'Failed to save API key', type: 'error' });
            }
        } catch (error) {
            setStatus({ message: 'Error connecting to server', type: 'error' });
        } finally {
            setStatus(prev => ({ ...prev, loading: false }));
        }
    };

    return (
        <Layout>
            <div className="p-8 max-w-4xl mx-auto">
                <div className="flex items-center space-x-4 mb-8">
                    <div className="p-3 bg-primary/10 rounded-xl">
                        <UserCog className="w-8 h-8 text-primary" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
                            Settings
                        </h1>
                        <p className="text-muted-foreground">Manage your API keys and application preferences</p>
                    </div>
                </div>

                <div className="space-y-6">
                    {/* API Key Section */}
                    <div className="bg-card border border-border/50 rounded-2xl p-6 shadow-sm backdrop-blur-sm">
                        <div className="flex items-center justify-between mb-6">
                            <div className="flex items-center space-x-3">
                                <Key className="w-5 h-5 text-indigo-500" />
                                <h2 className="text-xl font-semibold">Gemini API Configuration</h2>
                            </div>
                            <div className={`px-3 py-1 rounded-full text-xs font-medium flex items-center space-x-1 ${
                                keyStatus.isSet 
                                    ? 'bg-green-500/10 text-green-500 border border-green-500/20' 
                                    : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                            }`}>
                                {keyStatus.isSet ? (
                                    <><CheckCircle className="w-3 h-3" /><span>Active</span></>
                                ) : (
                                    <><AlertCircle className="w-3 h-3" /><span>Not Set</span></>
                                )}
                            </div>
                        </div>

                        {keyStatus.isSet && (
                            <div className="mb-6 p-4 bg-muted/50 rounded-lg border border-border/50">
                                <p className="text-sm text-muted-foreground mb-1">Current Key:</p>
                                <code className="text-sm font-mono text-primary">{keyStatus.maskedKey}</code>
                            </div>
                        )}

                        <form onSubmit={handleSave} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-2 pl-1">
                                    Update API Key
                                </label>
                                <div className="relative">
                                    <input
                                        type={showKey ? "text" : "password"}
                                        value={apiKey}
                                        onChange={(e) => setApiKey(e.target.value)}
                                        placeholder="Enter your Gemini API Key"
                                        className="w-full bg-background border border-border rounded-xl px-4 py-3 pr-12 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowKey(!showKey)}
                                        className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                    >
                                        {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                                <p className="text-xs text-muted-foreground mt-2 pl-1">
                                    Your key is stored locally in your .env file and never shared.
                                </p>
                            </div>

                            <div className="flex items-center justify-between pt-2">
                                {status.message && (
                                    <p className={`text-sm flex items-center ${
                                        status.type === 'success' ? 'text-green-500' : 'text-red-500'
                                    }`}>
                                        {status.type === 'success' ? (
                                            <CheckCircle className="w-4 h-4 mr-1.5" />
                                        ) : (
                                            <AlertCircle className="w-4 h-4 mr-1.5" />
                                        )}
                                        {status.message}
                                    </p>
                                )}
                                <button disbled={status.loading || !apiKey.trim()} 
                                    className={`ml-auto flex items-center space-x-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-all shadow-lg shadow-primary/20 ${
                                        (status.loading || !apiKey.trim()) ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'
                                    }`}
                                >
                                    <Save className="w-4 h-4" />
                                    <span>{status.loading ? 'Saving...' : 'Save Configuration'}</span>
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default Settings;
