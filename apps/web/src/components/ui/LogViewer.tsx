'use client';

import { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  command?: string;
  exitCode?: number;
}

interface LogViewerProps {
  logs: LogEntry[];
  autoScroll?: boolean;
  className?: string;
  maxHeight?: string;
}

export function LogViewer({ logs, autoScroll = true, className, maxHeight = '400px' }: LogViewerProps) {
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'text-red-400';
      case 'warn': return 'text-yellow-400';
      case 'debug': return 'text-gray-500';
      default: return 'text-gray-300';
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case 'error': return '✕';
      case 'warn': return '⚠';
      case 'debug': return '▸';
      default: return '▸';
    }
  };

  return (
    <div
      ref={logContainerRef}
      className={cn(
        'font-mono text-sm bg-gray-950 dark:bg-black rounded-lg p-4 overflow-y-auto',
        className
      )}
      style={{ maxHeight }}
      role="log"
      aria-live="polite"
    >
      {logs.length === 0 && (
        <div className="text-gray-500 text-center py-8">
          No logs yet...
        </div>
      )}
      {logs.map((log, index) => (
        <div key={index} className="mb-1 last:mb-0">
          <span className="text-gray-500 mr-2">[{log.timestamp}]</span>
          <span className={cn(getLevelColor(log.level), 'mr-2')}>{getLevelIcon(log.level)}</span>
          {log.command && (
            <>
              <span className="text-green-400 mr-1">$</span>
              <span className="text-blue-300 mr-2">{log.command}</span>
            </>
          )}
          <span className={cn(getLevelColor(log.level))}>{log.message}</span>
          {log.exitCode !== undefined && log.exitCode !== 0 && (
            <span className="ml-2 text-red-400">(exit code: {log.exitCode})</span>
          )}
        </div>
      ))}
    </div>
  );
}

interface DiffViewerProps {
  original: string;
  modified: string;
  filePath: string;
  className?: string;
}

export function DiffViewer({ original, modified, filePath, className }: DiffViewerProps) {
  const originalLines = original.split('\n');
  const modifiedLines = modified.split('\n');
  const maxLines = Math.max(originalLines.length, modifiedLines.length);

  return (
    <div className={cn('font-mono text-sm bg-gray-950 dark:bg-black rounded-lg overflow-hidden', className)}>
      <div className="px-4 py-2 bg-gray-800 border-b border-gray-700 text-gray-300">
        {filePath}
      </div>
      <div className="max-h-96 overflow-y-auto">
        <table className="w-full border-collapse">
          <tbody>
            {Array.from({ length: maxLines }, (_, i) => (
              <tr key={i}>
                <td className="w-8 text-right text-gray-500 px-2 py-0.5 border-r border-gray-800 select-none">
                  {i + 1}
                </td>
                <td className="w-8 text-right text-gray-500 px-2 py-0.5 border-r border-gray-800 select-none">
                  {originalLines[i] !== undefined ? i + 1 : ''}
                </td>
                <td className="w-8 text-right text-gray-500 px-2 py-0.5 border-r border-gray-800 select-none">
                  {modifiedLines[i] !== undefined ? i + 1 : ''}
                </td>
                <td className="px-4 py-0.5">
                  {originalLines[i] !== undefined && originalLines[i] !== modifiedLines[i] ? (
                    <div className="bg-red-900/30 text-red-300">
                      <span className="inline-block w-5">−</span>{' '}
                      {originalLines[i] || ' '}
                    </div>
                  ) : modifiedLines[i] !== undefined && originalLines[i] !== modifiedLines[i] ? (
                    <div className="bg-green-900/30 text-green-300">
                      <span className="inline-block w-5">+</span>{' '}
                      {modifiedLines[i] || ' '}
                    </div>
                  ) : (
                    <div className="text-gray-400">
                      <span className="inline-block w-5"> </span>{' '}
                      {originalLines[i] || modifiedLines[i] || ' '}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}