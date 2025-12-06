import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

const SmartSearch = ({ onSearch, isLoading, className }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  };

  return (
    <div className={cn("relative w-full max-w-2xl mx-auto group", className)}>
        {/* Glow Effect */}
      <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-600 rounded-xl blur opacity-30 group-hover:opacity-60 transition duration-500" />
      
      <form onSubmit={handleSubmit} className="relative flex items-center bg-background/80 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl overflow-hidden focus-within:ring-2 focus-within:ring-primary/50 transition-all">
        <div className="pl-4 text-muted-foreground group-focus-within:text-primary transition-colors">
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin text-primary" /> : <Search className="w-5 h-5" />}
        </div>
        
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for Stocks (e.g. RELIANCE, TCS)..."
          className="w-full bg-transparent border-none px-4 py-4 text-lg text-foreground placeholder-muted-foreground focus:outline-none focus:ring-0"
          disabled={isLoading}
        />
        
        <div className="pr-4 hidden sm:flex items-center gap-2">
            <kbd className="hidden md:inline-flex h-6 select-none items-center gap-1 rounded border border-border bg-muted px-2 text-[10px] font-medium text-muted-foreground opacity-100">
                <span className="text-xs">↵</span> Enter
            </kbd>
        </div>
      </form>
    </div>
  );
};

export default SmartSearch;
