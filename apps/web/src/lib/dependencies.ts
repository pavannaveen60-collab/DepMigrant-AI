export interface InspectedDependency {
  name: string;
  currentVersion: null;
  versionConstraint: string | null;
  manifest: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function parseInspectedDependencies(inspection: unknown): InspectedDependency[] {
  if (!isRecord(inspection) || !isRecord(inspection.dependencies)) return [];
  const manifests = inspection.dependencies;
  const found: InspectedDependency[] = [];
  const add = (name: string, versionConstraint: string, manifest: string) => {
    if (!found.some((item) => item.name.toLowerCase() === name.toLowerCase())) {
      found.push({
        name,
        currentVersion: null,
        versionConstraint: versionConstraint || null,
        manifest,
      });
    }
  };
  const parseLine = (entry: unknown, manifest: string) => {
    if (typeof entry !== 'string') return;
    const match = entry.trim().match(/^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]+\])?\s*(.*)$/);
    if (match) add(match[1], match[2].trim(), manifest);
  };

  const pyproject = manifests.pyproject_toml;
  if (isRecord(pyproject)) {
    if (Array.isArray(pyproject.dependencies)) {
      pyproject.dependencies.forEach((entry) => parseLine(entry, 'pyproject.toml'));
    }
    if (isRecord(pyproject.optional_dependencies)) {
      Object.values(pyproject.optional_dependencies).forEach((entries) => {
        if (Array.isArray(entries)) entries.forEach((entry) => parseLine(entry, 'pyproject.toml'));
      });
    }
    if (isRecord(pyproject.poetry) && isRecord(pyproject.poetry.dependencies)) {
      Object.entries(pyproject.poetry.dependencies).forEach(([name, value]) => {
        if (name.toLowerCase() === 'python') return;
        const version = typeof value === 'string'
          ? value
          : isRecord(value) && typeof value.version === 'string' ? value.version : '';
        add(name, version.trim(), 'pyproject.toml');
      });
    }
  }
  if (Array.isArray(manifests.requirements_txt)) {
    manifests.requirements_txt.forEach((entry) => parseLine(entry, 'requirements.txt'));
  }
  const setupPy = manifests.setup_py_dependencies;
  if (isRecord(setupPy)) {
    if (Array.isArray(setupPy.dependencies)) {
      setupPy.dependencies.forEach((entry) => parseLine(entry, 'setup.py'));
    }
    if (isRecord(setupPy.optional_dependencies)) {
      Object.values(setupPy.optional_dependencies).forEach((entries) => {
        if (Array.isArray(entries)) entries.forEach((entry) => parseLine(entry, 'setup.py'));
      });
    }
  }
  return found;
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!isRecord(error)) return fallback;
  if (
    error.code === 'ECONNABORTED' ||
    (typeof error.message === 'string' && error.message.toLowerCase().includes('timeout'))
  ) {
    return 'The migration plan request timed out while waiting for the AI provider. Please retry.';
  }
  if (!isRecord(error.response)) {
    if (typeof error.message === 'string' && error.message) {
      return error.message;
    }
    return fallback;
  }
  const data = error.response.data;
  if (isRecord(data)) {
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((entry) => {
          if (!isRecord(entry)) return null;
          const loc = Array.isArray(entry.loc) ? entry.loc.slice(1).join('.') : '';
          const msg = typeof entry.msg === 'string' ? entry.msg : 'Invalid value';
          if (loc === 'current_version' && msg.includes('pattern')) {
            return 'current_version must be a specific version number (e.g. 2.28.0), not a version constraint (e.g. >=2.28.0)';
          }
          if (loc === 'target_version' && msg.includes('pattern')) {
            return 'target_version must be a specific version number (e.g. 2.31.0), not a version constraint';
          }
          return loc ? `${loc}: ${msg}` : msg;
        })
        .filter(Boolean);
      if (messages.length > 0) return `Validation error: ${messages.join('; ')}`;
    }
    if (typeof data.message === 'string') return data.message;
  }
  const status = typeof error.response.status === 'number' ? error.response.status : null;
  if (status) {
    if (status === 504) {
      return 'The gateway timed out while waiting for the migration planner response. Please retry.';
    }
    if (status === 502) {
      return 'The backend received an invalid response from the upstream AI provider. Please retry.';
    }
    if (status === 503) {
      return 'The migration service or AI provider is temporarily unavailable. Please retry shortly.';
    }
    return `${fallback} (HTTP ${status})`;
  }
  return fallback;
}
