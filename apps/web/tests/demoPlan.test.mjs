import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { demoPlan } from '../src/lib/demoPlan.ts';

test('Try Demo reveals the demo content and Exit Demo hides it', async () => {
  const migrationPage = await readFile(
    new URL('../src/components/pages/MigrationPage.tsx', import.meta.url),
    'utf8',
  );
  const demoButton = migrationPage.indexOf('setDemoMode(true)');
  const demoSection = migrationPage.indexOf('{demoMode && <section');
  const normalForm = migrationPage.indexOf('STEP 1 · REPOSITORY');
  const exitButton = migrationPage.indexOf('onClick={() => setDemoMode(false)}');

  assert.notEqual(demoButton, -1, 'Try Demo should enable demo visibility');
  assert.notEqual(demoSection, -1, 'demo visibility should render the sample section');
  assert.ok(demoButton < demoSection && demoSection < normalForm, 'demo content should appear directly above the normal form');
  assert.notEqual(exitButton, -1, 'Exit Demo should disable demo visibility');
  assert.ok(migrationPage.includes('DEMO — SIMULATED DATA'));
  assert.ok(migrationPage.includes('Migration steps'));
  assert.ok(migrationPage.includes('Validation'));
  assert.ok(migrationPage.includes('Rollback guidance'));

  assert.equal(demoPlan.dependency.name, 'fastapi');
  assert.equal(demoPlan.dependency.currentVersion, '0.110.0');
  assert.equal(demoPlan.dependency.targetVersion, '0.115.0');
  assert.ok(demoPlan.breakingChangeExamples.length > 0);
  assert.ok(demoPlan.breakingChangeExamples.every((item) => item.startsWith('Example')));
  assert.ok(demoPlan.migrationSteps.length <= 5);
  assert.ok(demoPlan.validationChecks.length > 0);
  assert.ok(demoPlan.rollbackGuidance.length > 0);
});
