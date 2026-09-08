import React from 'react';
import { cn } from '../../utils/cn';

const VARIANTS = {
  primary:
    'bg-[var(--ink)] text-[var(--paper)] border-[var(--ink)] hover:bg-[var(--stamp)] hover:border-[var(--stamp)]',
  secondary:
    'bg-[var(--paper)] text-[var(--ink)] border-[var(--rule-strong)] hover:bg-[var(--paper-sunk)]',
  outline:
    'bg-transparent text-[var(--ink)] border-[var(--rule-strong)] hover:bg-[var(--paper-sunk)]',
  glass: 'bg-transparent text-[var(--ink)] border-[var(--rule-strong)] hover:bg-[var(--paper-sunk)]',
  ghost: 'bg-transparent text-[var(--ink-soft)] border-transparent hover:text-[var(--ink)] hover:bg-[var(--paper-sunk)]',
  danger:
    'bg-[var(--loss)] text-[var(--paper)] border-[var(--loss)] hover:brightness-110',
  approve:
    'bg-[var(--gain)] text-white border-[var(--gain)] hover:brightness-110',
};

// Mobile-first heights meet the 44px WCAG touch-target minimum; the sm:
// breakpoint reverts to the original compact sizing once a mouse/trackpad
// (not a fingertip) is the likely pointer.
const SIZES = {
  sm: 'h-11 sm:h-8 px-3 text-[0.6875rem]',
  md: 'h-11 sm:h-10 px-4 text-xs',
  lg: 'h-12 px-6 text-sm',
  icon: 'h-11 w-11 sm:h-9 sm:w-9',
};

const Button = React.forwardRef(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center gap-2 border font-[family-name:var(--font-narrow)] font-semibold uppercase tracking-[0.11em] transition-colors duration-150',
        'disabled:opacity-40 disabled:pointer-events-none',
        VARIANTS[variant] || VARIANTS.primary,
        SIZES[size] || SIZES.md,
        className
      )}
      {...props}
    />
  )
);
Button.displayName = 'Button';

export { Button };
