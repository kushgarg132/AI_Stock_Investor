import React from 'react';
import Sidebar from './layout/Sidebar';
import ChatWidget from './ChatWidget';
import { cn } from '../utils/cn';

const Layout = ({ children }) => {
  return (
    <div className="min-h-screen bg-background text-foreground font-sans selection:bg-primary/20">
      <Sidebar />
      
      {/* Main Content Wrapper */}
      <main className={cn(
        "transition-all duration-300 min-h-screen",
        "md:pl-64" // Push content for sidebar on desktop
      )}>
        <div className="container mx-auto p-6 md:p-8 max-w-7xl animate-in fade-in duration-500">
          {children}
        </div>
      </main>
      <ChatWidget />
    </div>
  );
};

export default Layout;
