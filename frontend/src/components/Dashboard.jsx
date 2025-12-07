import React, { useState, useEffect } from 'react';
import api, { endpoints } from '../utils/api';
import { useLocation } from 'react-router-dom';
import Layout from './Layout';
import SmartSearch from './dashboard/SmartSearch';
import MarketOverview from './dashboard/MarketOverview';
import TrendingStocks from './dashboard/TrendingStocks';
import WatchlistWidget from './dashboard/WatchlistWidget';
import AnalysisCard from './AnalysisCard';
import { Badge } from './common/Badge';
import { AlertCircle, Zap, Brain, ChartLine, Shield, TrendingUp } from 'lucide-react';

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Market Data State
  const [marketData, setMarketData] = useState({ indices: [], trending: [] });
  const [marketLoading, setMarketLoading] = useState(true);

  const location = useLocation();

  useEffect(() => {
    // Check for passed state from other pages
    if (location.state?.symbol) {
      handleSearch(location.state.symbol);
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // Fetch Market Data on Mount
  useEffect(() => {
      const fetchMarketData = async () => {
          try {
              const [indicesRes, trendingRes] = await Promise.all([
                  api.get(endpoints.marketIndices),
                  api.get(endpoints.trendingStocks)
              ]);
              setMarketData({
                  indices: indicesRes.data,
                  trending: trendingRes.data
              });
          } catch (e) {
              console.error("Failed to fetch market data:", e);
          } finally {
              setMarketLoading(false);
          }
      };
      
      fetchMarketData();
  }, []);

  const handleSearch = async (symbol) => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await api.post(endpoints.analyze(symbol));
      setData(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to fetch analysis. Ensure backend is running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="flex flex-col gap-8 min-h-[calc(100vh-100px)]">
        
        {/* Top Header Section (Only show when no data or loading) */}
        {!data && !loading && (
             <div className="space-y-8 animate-in fade-in slide-in-from-top-4 duration-700">
                <header className="text-center py-10">
                    <Badge variant="secondary" className="mb-4">
                        <Zap className="w-3 h-3 mr-1 text-yellow-400" />
                        v2.0 Beta Live
                    </Badge>
                    <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 text-balance">
                        <span className="bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent">
                            Financial Intelligence
                        </span>
                    </h1>
                    <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
                        Institutional-grade analysis powered by a multi-agent autonomous swarm.
                    </p>
                </header>

                <div className="flex justify-center">
                    <SmartSearch onSearch={handleSearch} isLoading={loading} className="max-w-xl w-full" />
                </div>

                <div className="pt-8 space-y-8">
                     <MarketOverview indices={marketData.indices} isLoading={marketLoading} />
                     
                     <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="md:col-span-2">
                            {/* Placeholder for broader market news or chart */}
                            <div className="h-full min-h-[300px] rounded-xl border border-border bg-card/50 flex items-center justify-center text-muted-foreground">
                                Market News Feed / Global Indices Chart
                            </div>
                        </div>
                        <div className="space-y-6">
                             <TrendingStocks 
                                stocks={marketData.trending} 
                                isLoading={marketLoading}
                                onStockClick={handleSearch} 
                             />
                             <WatchlistWidget />
                        </div>
                     </div>
                </div>
            </div>
        )}

        {/* Compressed Header when showing results */}
        {(data || loading) && (
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between pb-6 border-b border-border/50 animate-in fade-in">
                 <h2 className="text-2xl font-bold hidden md:block">Dashboard</h2>
                 <SmartSearch onSearch={handleSearch} isLoading={loading} className="w-full md:w-96" />
            </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mx-auto w-full max-w-2xl p-4 bg-destructive/10 border border-destructive/20 rounded-xl flex items-center gap-4 text-destructive animate-in fade-in">
             <AlertCircle className="w-5 h-5" />
             <p className="font-medium">{error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="flex-1 flex flex-col items-center justify-center py-20 animate-in fade-in duration-500">
              <div className="relative mb-8">
                <div className="w-20 h-20 rounded-full border-4 border-muted/30" />
                <div className="absolute inset-0 w-20 h-20 rounded-full border-4 border-transparent border-t-primary animate-spin" />
                <Brain className="absolute inset-0 m-auto w-8 h-8 text-primary animate-pulse" />
              </div>
              <h3 className="text-2xl font-bold mb-2">Analyzing Data</h3>
              <p className="text-muted-foreground">Orchestrating agents...</p>
          </div>
        )}

        {/* Results */}
        {!loading && data && (
          <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
            <AnalysisCard data={data} />
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
