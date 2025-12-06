import React, { useState } from 'react';
import axios from 'axios';
import Layout from './Layout';
import SearchBar from './SearchBar';
import AnalysisCard from './AnalysisCard';
import { AlertCircle } from 'lucide-react';

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async (symbol) => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      // Assuming backend is running on port 8001 as per previous context
      const response = await axios.post(`http://localhost:8001/api/v1/agents/analyze/${symbol}`);
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
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-center mb-10">
          <h2 className="text-4xl font-bold text-white mb-4">
            AI-Powered Market Intelligence
          </h2>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto">
            Enter a stock ticker to let our multi-agent system analyze market sentiment, 
            technical indicators, and risk factors in real-time.
          </p>
        </div>

        <SearchBar onSearch={handleSearch} isLoading={loading} />

        {error && (
          <div className="w-full max-w-2xl p-4 mb-8 bg-red-500/10 border border-red-500/30 rounded-xl flex items-center gap-3 text-red-400 animate-in fade-in slide-in-from-top-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center gap-4 animate-pulse">
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-slate-400 font-medium">Running Agent Workflow...</p>
            <div className="flex gap-2 text-xs text-slate-500">
              <span>Fetching News...</span>
              <span>•</span>
              <span>Analyzing Charts...</span>
              <span>•</span>
              <span>Calculating Risk...</span>
            </div>
          </div>
        )}

        <div className="w-full">
          <AnalysisCard data={data} />
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;
