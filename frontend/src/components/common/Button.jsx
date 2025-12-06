import React from 'react';
import { cn } from '../../utils/cn';

const Button = React.forwardRef(({ className, variant = 'primary', size = 'md', ...props }, ref) => {
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-500/20 border border-transparent',
    secondary: 'bg-slate-800 text-white hover:bg-slate-700 border border-slate-700',
    ghost: 'bg-transparent text-slate-400 hover:text-white hover:bg-white/5',
    danger: 'bg-red-500/10 text-red-500 hover:bg-red-500/20 border border-red-500/20',
    outline: 'bg-transparent border border-slate-700 text-slate-300 hover:text-white hover:border-slate-500',
    glass: 'bg-white/5 backdrop-blur-sm border border-white/10 text-white hover:bg-white/10'
  };

  const sizes = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
    icon: 'h-10 w-10 p-2 flex items-center justify-center'
  };

  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium transition-all focus:ring-2 focus:ring-blue-500/50 disabled:opacity-50 disabled:pointer-events-none active:scale-[0.98]',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
});

Button.displayName = 'Button';
export { Button };
