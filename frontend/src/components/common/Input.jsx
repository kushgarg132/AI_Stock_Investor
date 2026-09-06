import React from 'react';
import { cn } from '../../utils/cn';

/**
 * A field on the form: ruled underneath, not boxed in a rounded well.
 */
const Input = React.forwardRef(({ className, icon: Icon, ...props }, ref) => (
  <div className="relative flex items-center">
    {Icon && (
      <Icon className="absolute left-0 w-4 h-4 text-[var(--ink-faint)] pointer-events-none" />
    )}
    <input
      ref={ref}
      className={cn(
        'w-full bg-transparent border-0 border-b border-[var(--rule-strong)] py-2 text-sm text-[var(--ink)]',
        'focus:outline-none focus:border-[var(--stamp)] focus:ring-0',
        'disabled:opacity-40',
        Icon ? 'pl-6' : 'pl-0',
        className
      )}
      {...props}
    />
  </div>
));
Input.displayName = 'Input';

export { Input };
