'use client';

import { cn, getSeverityColor, getStatusColor } from '@/lib/utils';

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'status' | 'severity';
  status?: string;
  severity?: string;
}

export function Badge({ children, className, variant = 'default', status, severity }: BadgeProps) {
  let variantClass = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium';
  
  if (variant === 'status' && status) {
    variantClass += ` ${getStatusColor(status)}`;
  } else if (variant === 'severity' && severity) {
    variantClass += ` ${getSeverityColor(severity)}`;
  } else {
    variantClass += ' bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300';
  }

  return (
    <span className={cn(variantClass, className)}>
      {children}
    </span>
  );
}