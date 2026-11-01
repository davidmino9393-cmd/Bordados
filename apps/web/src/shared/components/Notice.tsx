import type { ReactNode } from 'react';

export const NoticeTone = {
  Info: 'info',
  Success: 'success',
  Warning: 'warning',
  Error: 'error',
} as const;
export type NoticeTone = (typeof NoticeTone)[keyof typeof NoticeTone];

interface NoticeProps {
  tone: NoticeTone;
  title?: string;
  children?: ReactNode;
}

export function Notice({ tone, title, children }: NoticeProps) {
  const role = tone === NoticeTone.Error ? 'alert' : 'status';
  return (
    <div className={`notice notice--${tone}`} role={role}>
      {title && <strong className="notice__title">{title}</strong>}
      {children && <div>{children}</div>}
    </div>
  );
}
