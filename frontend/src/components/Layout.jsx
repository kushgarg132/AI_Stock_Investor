import React from 'react';
import { TrendingUp, BarChart2, Sparkles, Settings, Wallet } from 'lucide-react';

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen animated-gradient text-white font-sans relative overflow-hidden">
      {/* Background decorations */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 -left-32 w-64 h-64 bg-blue-500/20 rounded-full blur-3xl float" />
        <div className="absolute top-1/2 -right-32 w-80 h-80 bg-purple-500/20 rounded-full blur-3xl float" style={{ animationDelay: '2s' }} />
        <div className="absolute bottom-1/4 left-1/3 w-48 h-48 bg-cyan-500/15 rounded-full blur-3xl float" style={{ animationDelay: '4s' }} />
      </div>
      
      {/* Header */}
      <header className="glass-strong sticky top-0 z-50 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {/* Logo */}
            <div className="relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 rounded-xl blur opacity-60 group-hover:opacity-100 transition duration-500" />
              <div className="relative w-10 h-10 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-xl flex items-center justify-center shadow-lg">
                <TrendingUp className="w-5 h-5 text-white" />
              </div>
            </div>
            <div>
              <h1 className="text-xl font-bold gradient-text">
                AI Stock Investor
              </h1>
              <p className="text-xs text-slate-400 -mt-0.5">Powered by Multi-Agent AI</p>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex items-center gap-2">
            <NavItem icon={<BarChart2 className="w-4 h-4" />} label="Dashboard" active />
            <NavItem icon={<Wallet className="w-4 h-4" />} label="Portfolio" />
            <NavItem icon={<Sparkles className="w-4 h-4" />} label="Insights" />
            <NavItem icon={<Settings className="w-4 h-4" />} label="Settings" />
          </nav>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
      
      {/* Footer */}
      <footer className="glass border-t border-white/5 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-center text-sm text-slate-500">
          <p>AI Stock Investor • Real-time Market Intelligence • Multi-Agent Analysis</p>
        </div>
      </footer>
    </div>
  );
};

const NavItem = ({ icon, label, active = false }) => (
  <button
    className={`
      flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200
      ${active 
        ? 'bg-gradient-to-r from-blue-600/80 to-purple-600/80 text-white shadow-lg glow-blue' 
        : 'text-slate-400 hover:text-white hover:bg-white/5'
      }
    `}
  >
    {icon}
    <span className="hidden sm:inline">{label}</span>
  </button>
);

export default Layout;
