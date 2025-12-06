import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw, TrendingUp, AlertTriangle, ArrowRight, Activity, Percent, ArrowUp, ArrowDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const ScannerPage = () => {
    const navigate = useNavigate();
    const [scanning, setScanning] = useState(false);
    const [results, setResults] = useState(null);
    const [error, setError] = useState(null);

    const runScan = async () => {
        setScanning(true);
        setError(null);
        try {
            const response = await axios.get('http://localhost:8000/api/v1/scanner/bullish');
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
        // Navigate to home with symbol query param or just navigate and let user type
        // For now, let's navigate to dashboard and maybe prepopulate if we can,
        // or just let user copy-paste. Ideally we pass state.
        navigate('/', { state: { symbol } });
    };

    return (
        <div className="min-h-screen bg-slate-900 text-white p-6">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-800 pb-6">
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent flex items-center gap-3">
                            <Activity className="w-8 h-8 text-blue-400" />
                            Indian Market Scanner
                        </h1>
                        <p className="text-slate-400 mt-2">
                            Scanning Small & Mid Cap stocks for bullish technical setups
                        </p>
                    </div>

                    <button
                        onClick={runScan}
                        disabled={scanning}
                        className={`px-6 py-3 rounded-xl font-semibold flex items-center gap-2 transition-all ${scanning
                                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 active:scale-95'
                            }`}
                    >
                        <RefreshCw className={`w-5 h-5 ${scanning ? 'animate-spin' : ''}`} />
                        {scanning ? 'Scanning Market...' : 'Scan Now'}
                    </button>
                </div>

                {/* Error Message */}
                {error && (
                    <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex items-center gap-3 text-red-400">
                        <AlertTriangle className="w-5 h-5" />
                        <p>{error}</p>
                    </div>
                )}

                {/* Loading State */}
                {scanning && !results && (
                    <div className="text-center py-20">
                        <div className="w-16 h-16 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin mx-auto mb-4"></div>
                        <p className="text-slate-400 animate-pulse">Analyzing technical indicators for 50+ stocks...</p>
                    </div>
                )}

                {/* Results Grid */}
                {results && results.bullish_picks.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {results.bullish_picks.map((stock) => (
                            <div
                                key={stock.symbol}
                                className="group bg-slate-800/50 backdrop-blur-sm border border-slate-700 hover:border-blue-500/50 rounded-2xl p-6 transition-all hover:shadow-xl hover:shadow-blue-500/10"
                            >
                                <div className="flex justify-between items-start mb-4">
                                    <div>
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="text-2xl font-bold text-white group-hover:text-blue-400 transition-colors">
                                                {stock.name}
                                            </h3>
                                            <span className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">NSE</span>
                                        </div>
                                        <span className="text-sm text-slate-400">{stock.symbol}</span>
                                    </div>
                                    <div className="text-right">
                                        <div className="text-xl font-bold text-white">
                                            ₹{stock.current_price.toLocaleString()}
                                        </div>
                                        <div className={`flex items-center justify-end gap-1 text-sm font-medium ${stock.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {stock.change_percent >= 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                                            {Math.abs(stock.change_percent)}%
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    {/* Confidence Meter */}
                                    <div>
                                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                                            <span>Signal Strength</span>
                                            <span className={getSignalColor(stock.signal_strength)}>{stock.confidence}% Confidence</span>
                                        </div>
                                        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full rounded-full ${stock.signal_strength >= 4 ? 'bg-green-500' : 'bg-blue-500'}`}
                                                style={{ width: `${stock.confidence}%` }}
                                            ></div>
                                        </div>
                                    </div>

                                    {/* Reasons */}
                                    <div className="bg-slate-900/50 rounded-xl p-3 border border-slate-700/50">
                                        <p className="text-xs text-slate-500 uppercase font-bold mb-2 tracking-wider">Bullish Signals</p>
                                        <ul className="space-y-1">
                                            {stock.reasons.map((reason, idx) => (
                                                <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                                                    <span className="text-green-400 mt-1">•</span>
                                                    {reason}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* Targets */}
                                    <div className="grid grid-cols-2 gap-3 pt-2">
                                        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-2 text-center">
                                            <p className="text-xs text-green-400 mb-0.5">Target</p>
                                            <p className="font-bold text-green-300">₹{stock.target_price}</p>
                                        </div>
                                        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
                                            <p className="text-xs text-red-400 mb-0.5">Stop Loss</p>
                                            <p className="font-bold text-red-300">₹{stock.stop_loss}</p>
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => analyzeStock(stock.symbol)}
                                        className="w-full mt-2 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition-colors flex items-center justify-center gap-2 group-hover:bg-blue-600"
                                    >
                                        Full Analysis <ArrowRight className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Empty State */}
                {results && results.bullish_picks.length === 0 && (
                    <div className="text-center py-20 bg-slate-800/30 rounded-3xl border-2 border-dashed border-slate-700">
                        <AlertTriangle className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                        <h3 className="text-xl font-bold text-white mb-2">No Bullish Signals Found</h3>
                        <p className="text-slate-400 max-w-md mx-auto">
                            The scanner didn't find any stocks matching our strict bullish criteria right now.
                            Try again later or check back when the market opens.
                        </p>
                        <button
                            onClick={runScan}
                            className="mt-6 px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                        >
                            Scan Again
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ScannerPage;
