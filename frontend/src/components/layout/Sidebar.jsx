import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  ScanLine, 
  Target, 
  LineChart, 
  Settings, 
  Wallet,
  BookMarked,
  Network 
} from 'lucide-react';
import { cn } from '../../utils/cn';

const Sidebar = () => {
  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
    { icon: ScanLine, label: 'Scanner', path: '/scanner' },
    { icon: Target, label: 'Goals', path: '/goals' },
    { icon: Network, label: 'System', path: '/system' },
    { icon: BookMarked, label: 'Watchlist', path: '/watchlist' }, // Placeholder
    { icon: Wallet, label: 'Portfolio', path: '/portfolio' }, // Placeholder
    { icon: Settings, label: 'Settings', path: '/settings' }, // Placeholder
  ];

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-card border-r border-border hidden md:flex flex-col z-50">
      {/* Logo Area */}
      <div className="h-16 flex items-center px-6 border-b border-border/50">
        <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                <LineChart className="w-5 h-5 text-primary" />
            </div>
            <span className="font-bold text-lg tracking-tight">StockAI</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-6 px-3 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) => cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all group",
              isActive 
                ? "bg-primary/10 text-primary" 
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            )}
          >
            <item.icon className="w-5 h-5 transition-colors" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      
      {/* User / Footer */}
      <div className="p-4 border-t border-border/50">
        <div className="flex items-center gap-3 p-2 rounded-lg bg-muted/30 border border-border/30">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500" />
            <div className="flex-1 overflow-hidden">
                <p className="text-sm font-medium truncate">Pro Investor</p>
                <p className="text-xs text-muted-foreground">Pro Plan</p>
            </div>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
