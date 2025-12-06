import React, { useState } from 'react';
import { Search, Sparkles, Zap } from 'lucide-react';

const SearchBar = ({ onSearch, isLoading }) => {
  const [symbol, setSymbol] = useState('');
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (symbol.trim()) {
      onSearch(symbol.toUpperCase());
    }
  };

  const popularSymbols = ['AAPL', 'GOOGL', 'TSLA', 'NVDA', 'MSFT'];

  return (
    <div className="w-full max-w-3xl mx-auto mb-12">
      <form onSubmit={handleSubmit}>
        <div className="relative group">
          {/* Animated glow background */}
          <div className={`
            absolute -inset-1 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 
            rounded-2xl opacity-0 group-hover:opacity-40 transition-all duration-500 blur-xl
            ${isFocused ? 'opacity-60' : ''}
          `} />
          
          {/* Animated border gradient */}
          <div className={`
            absolute -inset-0.5 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 
            rounded-2xl opacity-30 group-hover:opacity-60 transition-all duration-300
            ${isFocused ? 'opacity-80' : ''}
          `} />
          
          {/* Input container */}
          <div className="relative flex items-center glass-strong rounded-2xl p-2 shadow-2xl">
            <div className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-xl ml-2">
              <Search className="w-5 h-5 text-blue-400" />
            </div>
            
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder="Enter stock symbol..."
              className="flex-1 bg-transparent border-none focus:ring-0 text-xl text-white placeholder-slate-500 px-4 py-3 font-medium tracking-wide"
              disabled={isLoading}
            />
            
            <button
              type="submit"
              disabled={isLoading || !symbol}
              className={`
                relative overflow-hidden px-8 py-3 rounded-xl font-semibold text-white
                transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed
                ${isLoading 
                  ? 'bg-gradient-to-r from-purple-600 to-pink-600' 
                  : 'bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 hover:shadow-lg hover:shadow-purple-500/30 hover:scale-105'
                }
              `}
            >
              <span className="relative z-10 flex items-center gap-2">
                {isLoading ? (
                  <>
                    <Zap className="w-5 h-5 animate-pulse" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5" />
                    Analyze
                  </>
                )}
              </span>
              {!isLoading && (
                <div className="absolute inset-0 bg-gradient-to-r from-pink-600 via-purple-600 to-blue-600 opacity-0 hover:opacity-100 transition-opacity duration-300" />
              )}
            </button>
          </div>
        </div>
      </form>
      
      {/* Quick select chips */}
      <div className="flex flex-wrap items-center justify-center gap-2 mt-6">
        <span className="text-xs text-slate-500 uppercase tracking-wider mr-2">Popular:</span>
        {popularSymbols.map((sym) => (
          <button
            key={sym}
            onClick={() => { setSymbol(sym); onSearch(sym); }}
            disabled={isLoading}
            className="px-4 py-1.5 rounded-full text-sm font-medium bg-white/5 border border-white/10 
                       text-slate-400 hover:text-white hover:bg-white/10 hover:border-white/20 
                       transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sym}
          </button>
        ))}
      </div>
    </div>
  );
};

export default SearchBar;
