import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw, TrendingUp, AlertTriangle, ArrowRight, Activity, Percent, ArrowUp, ArrowDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout';

const ScannerPage = () => {
    const navigate = useNavigate();
    const [scanning, setScanning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);

    const runScan = async () => {
        setScanning(true);
        setError(null);
        try {
            const response = await axios.get('http://localhost:8001/api/v1/scanner/bullish');
            setResults(response.data);
        } catch (err) {
            setError('Failed to scan stocks. Please try again.');
            console.error(err);
        } finally {
            setScanning(false);
        }
    };

    // Auto-run scan on first load if no results
    useEffect(() => {
        if (!results && !scanning) {
            runScan();
        }
    }, []);

    const getSignalColor = (strength) => {
        if (strength >= 4) return 'text-green-400';
        if (strength === 3) return 'text-blue-400';
        return 'text-yellow-400';
    };

    const analyzeStock = (symbol) => {
        navigate('/', { state: { symbol } });
    };

    return (
        <Layout>
            <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">

                {/* Header Section */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
                                <Activity className="w-6 h-6" />
                            </div>
                            <h1 className="text-3xl font-bold text-white">
                                Market Scanner
                            </h1>
                        </div>
                        <p className="text-slate-400 text-lg">
                            Real-time analysis of Small & Mid Cap stocks for bullish setups
                        </p>
                    </div>

                    <button
                        onClick={runScan}
                        disabled={scanning}
                        className={`px-6 py-3 rounded-xl font-bold flex items-center gap-2 transition-all shadow-lg ${scanning
                            ? 'bg-slate-800 text-slate-500 cursor-not-allowed shadow-none'
                            : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-blue-500/25 active:scale-95'
                            }`}
                    >
                        <RefreshCw className={`w-5 h-5 ${scanning ? 'animate-spin' : ''}`} />
                        {scanning ? 'Scanning Market...' : 'Scan Now'}
                    </button>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-2xl p-4 flex items-center gap-3 text-red-400 animate-in slide-in-from-top-2">
                        <AlertTriangle className="w-5 h-5" />
                        <p>{error}</p>
                    </div>
                )}

                {/* Loading State */}
                {scanning && !results && (
                    <div className="text-center py-24 glass rounded-3xl border border-white/5">
                        <div className="relative w-20 h-20 mx-auto mb-6">
                            <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full"></div>
                            <div className="absolute inset-0 border-4 border-t-blue-500 rounded-full animate-spin"></div>
                            <Activity className="absolute inset-0 m-auto w-8 h-8 text-blue-400 animate-pulse" />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">Analyzing Market Data</h3>
                        <p className="text-slate-400 animate-pulse">Scanning technical indicators for 50+ stocks...</p>
                    </div>
                )}

                {/* Results Grid */}
                {results && results.bullish_picks.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {results.bullish_picks.map((stock, index) => (
                            <div
                                key={stock.symbol}
                                className="group bg-slate-800/40 backdrop-blur-md border border-white/10 hover:border-blue-500/50 rounded-2xl p-6 transition-all hover:shadow-xl hover:shadow-blue-500/10 hover:-translate-y-1"
                                style={{ animationDelay: `${index * 100}ms` }}
                            >
                                <div className="flex justify-between items-start mb-5">
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="text-xl font-bold text-white group-hover:text-blue-400 transition-colors">
                                                {stock.name}
                                            </h3>
                                            <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-700/50 text-slate-300 px-2 py-0.5 rounded-full border border-white/5">NSE</span>
                                        </div>
                                        <span className="text-sm text-slate-400 font-medium">{stock.symbol}</span>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-2xl font-bold text-white tracking-tight">
                                            ₹{stock.current_price.toLocaleString()}
                                        </div>
                                        <div className={`flex items-center justify-end gap-1 text-sm font-bold ${stock.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {stock.change_percent >= 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                                            {Math.abs(stock.change_percent)}%
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-5">
                                    {/* Confidence Meter */}
                                    <div>
                                        <div className="flex justify-between text-xs font-semibold text-slate-400 mb-2">
                                            <span>SIGNAL STRENGTH</span>
                                            <span className={getSignalColor(stock.signal_strength)}>{stock.confidence}% CONFIDENCE</span>
                                        </div>
                                        <div className="h-2 bg-slate-700/50 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full transition-all duration-1000 ${stock.signal_strength >= 4 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : 'bg-gradient-to-r from-blue-500 to-indigo-500'}`}
                                                style={{ width: `${stock.confidence}%` }}
                                            ></div>
                                        </div>
                                    </div>

                                    {/* Reasons */}
                                    <div className="bg-slate-900/50 rounded-xl p-3 border border-white/5">
                                        <p className="text-xs text-slate-500 uppercase font-bold mb-3 tracking-wider flex items-center gap-1">
                                            <TrendingUp className="w-3 h-3" /> Bullish Drivers
                                        </p>
                                        <ul className="space-y-2">
                                            {stock.reasons.map((reason, idx) => (
                                                <li key={idx} className="text-sm text-slate-300 flex items-start gap-2 leading-snug">
                                                    <span className="text-green-400 mt-0.5">•</span>
                                                    {reason}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* Targets */}
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-2.5 text-center group/target hover:bg-green-500/10 transition-colors">
                                            <p className="text-[10px] uppercase font-bold text-green-500/70 mb-0.5">Target Price</p>
                                            <p className="font-bold text-green-400">₹{stock.target_price}</p>
                                        </div>
                                        <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-2.5 text-center group/stop hover:bg-red-500/10 transition-colors">
                                            <p className="text-[10px] uppercase font-bold text-red-500/70 mb-0.5">Stop Loss</p>
                                            <p className="font-bold text-red-400">₹{stock.stop_loss}</p>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => analyzeStock(stock.symbol)}
                                        className="w-full py-3 bg-white/5 hover:bg-blue-600 hover:text-white text-slate-300 rounded-xl font-bold transition-all flex items-center justify-center gap-2 group-hover:shadow-lg group-hover:shadow-blue-500/20 border border-white/5 hover:border-transparent"
                                    >
                                        Deep Analysis <ArrowRight className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Empty State */}
                {results && results.bullish_picks.length === 0 && (
                    <div className="text-center py-20 bg-slate-800/30 rounded-3xl border-2 border-dashed border-slate-700/50">
                        <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
                            <Activity className="w-8 h-8 text-slate-600" />
                        </div>
                        <h3 className="text-xl font-bold text-white mb-2">No High-Conviction Signals</h3>
                        <p className="text-slate-400 max-w-md mx-auto leading-relaxed">
                            Our algorithms didn't find any stocks matching strict bullish criteria right now.
                            The market might be sideways or bearish.
                        </p>
                        <button
                            onClick={runScan}
                            className="mt-8 px-8 py-3 bg-white/5 hover:bg-white/10 text-white rounded-xl font-bold transition-colors border border-white/10"
                        >
                            Run Fresh Scan
                        </button>
                    </div>
                )}
            </div>
        </Layout>
    );
};

export default ScannerPage;
