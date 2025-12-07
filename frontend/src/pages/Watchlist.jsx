import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/common/Card';
import api, { endpoints } from '../utils/api';
import { Trash2, TrendingUp, TrendingDown, ArrowRight, Loader2 } from 'lucide-react';
import { Badge } from '../components/common/Badge';
import { useNavigate } from 'react-router-dom';

const Watchlist = () => {
    const [watchlist, setWatchlist] = useState([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    const userId = "default-user"; // Hardcoded for single user mode

    useEffect(() => {
        fetchWatchlist();
    }, []);

    const fetchWatchlist = async () => {
        try {
            const res = await api.get(endpoints.watchlist.details(userId));
            setWatchlist(res.data);
        } catch (error) {
            console.error("Failed to fetch watchlist:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleRemove = async (e, symbol) => {
        e.stopPropagation();
        try {
            await api.delete(endpoints.watchlist.remove(userId, symbol));
            // Optimistic update
            setWatchlist(prev => prev.filter(item => item.symbol !== symbol));
        } catch (error) {
            console.error("Failed to remove from watchlist:", error);
        }
    };

    const handleAnalyze = (symbol) => {
        navigate('/', { state: { symbol } });
    };

    if (loading) {
        return (
            <Layout>
                <div className="flex flex-col items-center justify-center min-h-[60vh]">
                    <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
                    <p className="text-muted-foreground">Loading watchlist...</p>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">Your Watchlist</h1>
                        <p className="text-muted-foreground mt-1">
                            Tracking {watchlist.length} companies
                        </p>
                    </div>
                </div>

                {watchlist.length === 0 ? (
                    <div className="text-center py-20 border border-dashed border-border rounded-xl">
                        <p className="text-muted-foreground text-lg mb-4">Your watchlist is empty.</p>
                        <p className="text-sm text-muted-foreground/80">
                            Search for stocks in the Dashboard and add them here to track performance.
                        </p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {watchlist.map((stock) => (
                            <Card 
                                key={stock.symbol} 
                                className="group hover:border-primary/50 transition-all cursor-pointer overflow-hidden"
                                onClick={() => handleAnalyze(stock.symbol)}
                            >
                                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 bg-muted/20">
                                    <div className="flex flex-col">
                                        <CardTitle className="text-lg font-bold">{stock.symbol}</CardTitle>
                                        <span className="text-xs text-muted-foreground">{stock.name}</span>
                                    </div>
                                    <Badge variant={stock.day_change >= 0 ? "success" : "destructive"}>
                                        {stock.day_change >= 0 ? "+" : ""}{stock.day_change_percent?.toFixed(2)}%
                                    </Badge>
                                </CardHeader>
                                <CardContent className="pt-4">
                                    <div className="flex justify-between items-end mb-4">
                                        <div>
                                            <div className="text-2xl font-bold">
                                                ${stock.current_price?.toFixed(2)}
                                            </div>
                                            <div className="text-xs text-muted-foreground flex items-center mt-1">
                                                {stock.day_change >= 0 ? (
                                                    <TrendingUp className="w-3 h-3 text-green-500 mr-1" />
                                                ) : (
                                                    <TrendingDown className="w-3 h-3 text-red-500 mr-1" />
                                                )}
                                                {stock.day_change >= 0 ? "+" : ""}{stock.day_change?.toFixed(2)} Today
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <div className="flex items-center justify-between pt-4 border-t border-border/50">
                                        <button 
                                            onClick={(e) => handleRemove(e, stock.symbol)}
                                            className="text-muted-foreground hover:text-destructive transition-colors p-2 -ml-2 rounded-md hover:bg-destructive/10"
                                            title="Remove from watchlist"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                        
                                        <div className="flex items-center text-primary text-sm font-medium group-hover:translate-x-1 transition-transform">
                                            Analyze <ArrowRight className="w-4 h-4 ml-1" />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </div>
        </Layout>
    );
};

export default Watchlist;
