import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import Layout from './Layout';
import SearchBar from './SearchBar';
import AnalysisCard from './AnalysisCard';
import { AlertCircle, Zap, Brain, ChartLine, Shield, Activity } from 'lucide-react';

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const location = useLocation();

  useEffect(() => {
    if (location.state?.symbol) {
      handleSearch(location.state.symbol);
      // Clear state so it doesn't re-run on refresh
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const handleSearch = async (symbol) => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await axios.post(`http://localhost:8000/api/v1/agents/analyze/${symbol}`);
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
      <div className="flex flex-col items-center">
        {/* Hero Section */}
        <div className="text-center mb-12 max-w-4xl">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 mb-6">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-sm text-slate-300">Powered by Multi-Agent AI Architecture</span>
          </div>

          <h2 className="text-5xl md:text-6xl font-bold mb-6">
            <span className="gradient-text">Intelligent Stock</span>
            <br />
            <span className="text-white">Analysis Platform</span>
          </h2>

          <p className="text-slate-400 text-lg md:text-xl max-w-2xl mx-auto leading-relaxed">
            Enter any stock ticker and let our AI agents analyze market sentiment,
            technical indicators, and risk factors in real-time.
          </p>
        </div>

        {/* Search Bar */}
        <SearchBar onSearch={handleSearch} isLoading={loading} />

        {/* Error State */}
        {error && (
          <div className="w-full max-w-2xl p-5 mb-8 glass rounded-2xl border border-red-500/30 flex items-center gap-4 animate-in fade-in slide-in-from-top-2">
            <div className="w-12 h-12 rounded-xl bg-red-500/20 flex items-center justify-center flex-shrink-0">
              <AlertCircle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <h4 className="font-semibold text-red-400">Analysis Failed</h4>
              <p className="text-sm text-red-400/80">{error}</p>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="w-full max-w-4xl py-16 animate-in fade-in duration-500">
            <div className="flex flex-col items-center gap-8">
              {/* Animated loader */}
              <div className="relative">
                <div className="w-24 h-24 rounded-full border-4 border-slate-700" />
                <div className="absolute inset-0 w-24 h-24 rounded-full border-4 border-transparent border-t-blue-500 border-r-purple-500 animate-spin" />
                <div className="absolute inset-2 w-20 h-20 rounded-full border-4 border-transparent border-b-pink-500 border-l-cyan-500 animate-spin" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Brain className="w-8 h-8 text-purple-400 animate-pulse" />
                </div>
              </div>

              <div className="text-center">
                <h3 className="text-2xl font-bold text-white mb-2">Analyzing Market Data</h3>
                <p className="text-slate-400">Multi-agent system processing your request</p>
              </div>

              {/* Agent steps */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-3xl">
                <AgentStep
                  icon={<Zap className="w-5 h-5" />}
                  label="Fetching Data"
                  color="blue"
                  delay={0}
                />
                <AgentStep
                  icon={<Brain className="w-5 h-5" />}
                  label="Sentiment Analysis"
                  color="cyan"
                  delay={1}
                />
                <AgentStep
                  icon={<ChartLine className="w-5 h-5" />}
                  label="Technical Analysis"
                  color="purple"
                  delay={2}
                />
                <AgentStep
                  icon={<Shield className="w-5 h-5" />}
                  label="Risk Assessment"
                  color="pink"
                  delay={3}
                />
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {!loading && data && (
          <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-700">
            <AnalysisCard data={data} />
          </div>
        )}

        {/* Empty state with features */}
        {!loading && !data && !error && (
          <div className="w-full max-w-4xl mt-8 animate-in fade-in duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div
                onClick={() => window.location.href = '/scanner'}
                className="group p-6 rounded-2xl bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-blue-500/30 card-hover cursor-pointer relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 to-purple-600/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center mb-4 shadow-lg shadow-blue-500/20">
                  <Activity className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                  Market Scanner
                  <span className="flex h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                </h3>
                <p className="text-sm text-blue-200/80 leading-relaxed">
                  Find stocks with bullish signals in real-time. Scan Nifty Small & Midcap.
                </p>
              </div>

              <FeatureCard
                icon={<Brain className="w-6 h-6" />}
                title="Sentiment Analysis"
                description="AI-powered analysis of news and social media for market sentiment"
                color="cyan"
              />
              <FeatureCard
                icon={<ChartLine className="w-6 h-6" />}
                title="Technical Signals"
                description="Advanced pattern recognition and technical indicator analysis"
                color="purple"
              />
              <FeatureCard
                icon={<Shield className="w-6 h-6" />}
                title="Risk Management"
                description="Smart position sizing and risk-adjusted trade recommendations"
                color="pink"
              />
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

const AgentStep = ({ icon, label, color, delay }) => {
  const colorClasses = {
    blue: 'from-blue-500/20 to-blue-600/20 text-blue-400 border-blue-500/30',
    cyan: 'from-cyan-500/20 to-cyan-600/20 text-cyan-400 border-cyan-500/30',
    purple: 'from-purple-500/20 to-purple-600/20 text-purple-400 border-purple-500/30',
    pink: 'from-pink-500/20 to-pink-600/20 text-pink-400 border-pink-500/30',
  };

  return (
    <div
      className={`p-4 rounded-xl glass border ${colorClasses[color]} flex flex-col items-center gap-2 shimmer`}
      style={{ animationDelay: `${delay * 0.3}s` }}
    >
      <div className={`p-2 rounded-lg bg-gradient-to-br ${colorClasses[color]}`}>
        {icon}
      </div>
      <span className="text-sm font-medium text-slate-300">{label}</span>
    </div>
  );
};

const FeatureCard = ({ icon, title, description, color }) => {
  const colorClasses = {
    cyan: 'from-cyan-500 to-cyan-600 group-hover:shadow-cyan-500/20',
    purple: 'from-purple-500 to-purple-600 group-hover:shadow-purple-500/20',
    pink: 'from-pink-500 to-pink-600 group-hover:shadow-pink-500/20',
  };

  return (
    <div className="group p-6 rounded-2xl glass border border-white/5 card-hover cursor-pointer">
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${colorClasses[color]} flex items-center justify-center mb-4 shadow-lg transition-shadow group-hover:shadow-xl`}>
        <div className="text-white">{icon}</div>
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
    </div>
  );
};

export default Dashboard;
