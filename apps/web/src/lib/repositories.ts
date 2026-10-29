import type { Repository } from '@/types';

export function uniqueRepositories(repositories: Repository[]): Repository[] {
  const seen = new Set<string>();
  return repositories.filter((repository) => {
    // Git identity is the exact trimmed URL plus branch (missing branch means main); archives are ID-based.
    const identity = repository.type === 'git' && repository.url
      ? `git:${repository.url.trim()}#${repository.branch?.trim() || 'main'}`
      : `record:${repository.id}`;
    if (seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}
