import React from 'react';
import { cn } from '../../utils/cn';

/**
 * A field mark on the form: boxed, tracked, upper. Not a pill — nothing in a
 * printed document has a rounded end.
 */
const VARIANTS = {
  default: 'border-[var(--rule-strong)] text-[var(--ink)]',
  secondary: 'border-[var(--rule)] text-[var(--ink-soft)]',
  outline: 'border-[var(--rule)] text-[var(--ink-soft)]',
  neutral: 'border-[var(--rule)] text-[var(--ink-soft)]',
  success: 'border-[var(--gain)] text-[var(--gain)] bg-[var(--gain-wash)]',
  destructive: 'border-[var(--loss)] text-[var(--loss)] bg-[var(--loss-wash)]',
  warning: 'border-[var(--stamp)] text-[var(--stamp)] bg-[var(--stamp-soft)]',
  stamp: 'border-[var(--stamp)] text-[var(--stamp)] bg-[var(--stamp-soft)]',
};

const Badge = ({ className, variant = 'default', ...props }) => (
  <span
    className={cn(
      'inline-flex items-center gap-1 border px-1.5 py-0.5 font-[family-name:var(--font-narrow)] text-[0.625rem] font-semibold uppercase tracking-[0.11em] leading-none',
      VARIANTS[variant] || VARIANTS.default,
      className
    )}
    {...props}
  />
);

export { Badge };
