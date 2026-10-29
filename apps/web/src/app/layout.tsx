import type { Metadata } from 'next';
import { WorkspaceShell } from '@/components/WorkspaceShell';
import './globals.css';

export const metadata: Metadata = {
  title: 'DepMigrant AI — Upgrade with Confidence',
  description: 'Review dependency migration plans and verification evidence in one careful workspace.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body><WorkspaceShell>{children}</WorkspaceShell></body>
    </html>
  );
}