import type { ReactNode } from 'react';

export function PageHeader({ eyebrow, title, description, action }: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="workspace-page-header">
      <div>
        <p className="eyebrow"><span className="eyebrow-line" /> {eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="workspace-page-action">{action}</div>}
    </div>
  );
}
