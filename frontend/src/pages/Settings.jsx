import React, { useState, useEffect, useMemo } from 'react';
import Layout from '../components/Layout';
import { UserCog, Cpu, Save, CheckCircle, AlertCircle, Search } from 'lucide-react';
import api, { endpoints } from '../utils/api';

const Settings = () => {
    const [models, setModels] = useState([]);
    const [currentModel, setCurrentModel] = useState('');
    const [query, setQuery] = useState('');
    const [selectedModel, setSelectedModel] = useState('');
    const [dropdownOpen, setDropdownOpen] = useState(false);
    const [status, setStatus] = useState({ loading: false, message: '', type: '' });
    const [loadError, setLoadError] = useState('');

    useEffect(() => {
        let cancelled = false;
        (async () => {
            try {
                const [modelsRes, currentRes] = await Promise.all([
                    api.get(endpoints.settings.omnirouteModels),
                    api.get(endpoints.settings.omnirouteModel),
                ]);
                if (cancelled) return;
                setModels(modelsRes.data);
                setCurrentModel(currentRes.data.model);
                setSelectedModel(currentRes.data.model);
                setLoadError('');
            } catch {
                if (!cancelled) setLoadError('Could not load models from the OmniRoute gateway.');
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const filteredModels = useMemo(() => {
        if (!query.trim()) return models;
        const q = query.trim().toLowerCase();
        return models.filter((m) => m.id.toLowerCase().includes(q));
    }, [models, query]);

    const handleSave = async () => {
        if (!selectedModel.trim()) return;
        setStatus({ loading: true, message: '', type: '' });
        try {
            await api.post(endpoints.settings.omnirouteModel, { model: selectedModel });
            setStatus({ loading: false, message: 'Model saved successfully!', type: 'success' });
            setCurrentModel(selectedModel);
        } catch {
            setStatus({ loading: false, message: 'Failed to save model', type: 'error' });
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
                        <h1 className="text-3xl font-bold">Settings</h1>
                        <p className="text-muted-foreground">Manage your application preferences</p>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="bg-card border border-border/50 rounded-2xl p-6 shadow-sm backdrop-blur-sm">
                        <div className="flex items-center space-x-3 mb-6">
                            <Cpu className="w-5 h-5 text-indigo-500" />
                            <h2 className="text-xl font-semibold">OmniRoute Model</h2>
                        </div>

                        {loadError ? (
                            <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-center gap-3 text-destructive">
                                <AlertCircle className="w-5 h-5" />
                                <p className="text-sm">{loadError}</p>
                            </div>
                        ) : (
                            <>
                                {currentModel && (
                                    <div className="mb-6 p-4 bg-muted/50 rounded-lg border border-border/50">
                                        <p className="text-sm text-muted-foreground mb-1">Current Model:</p>
                                        <code className="text-sm font-mono text-primary">{currentModel}</code>
                                    </div>
                                )}

                                <div className="relative">
                                    <label className="block text-sm font-medium mb-2 pl-1">Select Model</label>
                                    <div className="relative">
                                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <input
                                            type="text"
                                            value={dropdownOpen ? query : selectedModel}
                                            onFocus={() => { setDropdownOpen(true); setQuery(''); }}
                                            onBlur={() => setTimeout(() => setDropdownOpen(false), 150)}
                                            onChange={(e) => setQuery(e.target.value)}
                                            placeholder="Search models (e.g. claude, gemini)..."
                                            className="w-full bg-background border border-border rounded-xl pl-11 pr-4 py-3 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                        />
                                    </div>
                                    {dropdownOpen && (
                                        <div className="absolute z-10 mt-1 w-full max-h-64 overflow-y-auto rounded-xl border border-border bg-popover shadow-xl custom-scrollbar">
                                            {filteredModels.length === 0 ? (
                                                <p className="px-4 py-3 text-sm text-muted-foreground">No matching models</p>
                                            ) : (
                                                filteredModels.slice(0, 100).map((m) => (
                                                    <button
                                                        key={m.id}
                                                        type="button"
                                                        onMouseDown={(e) => e.preventDefault()}
                                                        onClick={() => {
                                                            setSelectedModel(m.id);
                                                            setDropdownOpen(false);
                                                        }}
                                                        className="w-full text-left px-4 py-2.5 text-sm font-mono hover:bg-muted/50 transition-colors"
                                                    >
                                                        {m.id}
                                                    </button>
                                                ))
                                            )}
                                        </div>
                                    )}
                                </div>

                                <div className="flex items-center justify-between pt-6">
                                    {status.message && (
                                        <p className={`text-sm flex items-center ${status.type === 'success' ? 'text-green-500' : 'text-red-500'}`}>
                                            {status.type === 'success' ? (
                                                <CheckCircle className="w-4 h-4 mr-1.5" />
                                            ) : (
                                                <AlertCircle className="w-4 h-4 mr-1.5" />
                                            )}
                                            {status.message}
                                        </p>
                                    )}
                                    <button
                                        onClick={handleSave}
                                        disabled={status.loading || !selectedModel.trim() || selectedModel === currentModel}
                                        className={`ml-auto flex items-center space-x-2 px-6 py-2.5 bg-primary text-primary-foreground rounded-xl hover:bg-primary/90 transition-all shadow-lg shadow-primary/20 ${
                                            (status.loading || !selectedModel.trim() || selectedModel === currentModel) ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'
                                        }`}
                                    >
                                        <Save className="w-4 h-4" />
                                        <span>{status.loading ? 'Saving...' : 'Save Model'}</span>
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </Layout>
    );
};

export default Settings;
