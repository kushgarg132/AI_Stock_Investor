import React from 'react';
import { cn } from '../../utils/cn';

const Input = React.forwardRef(({ className, type, icon, ...props }, ref) => {
  return (
    <div className="relative w-full">
        {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                {icon}
            </div>
        )}
      <input
        type={type}
        className={cn(
          'flex h-10 w-full rounded-lg border border-input bg-background/50 px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 transition-all focus:bg-background',
          icon && "pl-10",
          className
        )}
        ref={ref}
        {...props}
      />
    </div>
  );
});
Input.displayName = 'Input';

export { Input };
