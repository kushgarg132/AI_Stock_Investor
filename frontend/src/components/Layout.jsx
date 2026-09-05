import React from 'react';
// `motion` is used via JSX (<motion.div>) -- this project has no eslint-plugin-react
// installed to teach no-unused-vars that pattern.
// eslint-disable-next-line no-unused-vars
import { motion } from 'framer-motion';
import Sidebar from './layout/Sidebar';
import ChatWidget from './ChatWidget';
import { cn } from '../utils/cn';
import { Menu } from 'lucide-react';

const Layout = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = React.useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground font-sans selection:bg-primary/20">
      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-background/80 backdrop-blur-md border-b border-border h-16 px-4 flex items-center justify-between">
        <button 
          onClick={() => setIsSidebarOpen(true)}
          className="p-2 hover:bg-muted/50 rounded-md"
        >
          <Menu className="w-6 h-6" />
        </button>
        <span className="font-bold text-lg tracking-tight">NeoTrade AI</span>
        <div className="w-10" /> {/* Spacer for centering if needed, or user icon */}
      </div>

      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      
      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Main Content Wrapper */}
      <main className={cn(
        "transition-all duration-300 min-h-screen pt-16 md:pt-0", // Add padding-top on mobile for header
        "md:pl-64" // Push content for sidebar on desktop
      )}>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="container mx-auto p-4 md:p-8 max-w-7xl"
        >
          {children}
        </motion.div>
      </main>
      <ChatWidget />
    </div>
  );
};

export default Layout;
