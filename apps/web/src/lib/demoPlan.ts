export const demoPlan = {
  dependency: {
    name: 'fastapi',
    currentVersion: '0.110.0',
    targetVersion: '0.115.0',
  },
  breakingChangeExamples: [
    'Example consideration: review framework lifecycle and startup hooks for behavior changes.',
    'Example consideration: check integrations and plugins for compatibility with the target release.',
  ],
  migrationSteps: [
    'Review the dependency declaration and confirm the actual installed version.',
    'Update the version constraint in a working branch, then inspect the resulting diff.',
    'Run the project test suite and manually verify application startup before release.',
  ],
  validationChecks: [
    'Dependency resolution completes without conflicts.',
    'Automated tests pass on the target version.',
    'Application startup and key API flows are manually verified.',
  ],
  rollbackGuidance: [
    'Keep the change on a dedicated branch and preserve the original dependency declaration.',
    'If validation fails, restore the original declaration and rerun the baseline checks.',
  ],
} as const;
