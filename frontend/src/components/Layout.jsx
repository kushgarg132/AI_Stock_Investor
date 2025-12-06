import React from 'react';

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-slate-900 text-white font-sans">
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <span className="text-xl font-bold">AI</span>
            </div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent whitespace-nowrap">
              Stock Investor
            </h1>
          </div>
          <nav>
            <ul className="flex flex-wrap justify-center gap-4 sm:gap-6 text-sm font-medium text-slate-400">
              <li className="hover:text-white cursor-pointer transition-colors">Dashboard</li>
              <li className="hover:text-white cursor-pointer transition-colors">Portfolio</li>
              <li className="hover:text-white cursor-pointer transition-colors">Settings</li>
            </ul>
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;
