// OPTIONAL add-on, not the default (references/goal-tests.md#optional-self-healing-agent-steps-with-e2e). It needs a model
// API key in CI; a Claude subscription does not work with e2e. Copy it to the app folder as e2e.config.ts.
// Replace every REPLACE. The e2e docs ship in node_modules/e2e/docs (reference/config.mdx lists every key).
import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';
import { gateway } from 'ai';

// Send no anonymous usage data. CI also sets E2E_TELEMETRY_DISABLED=1 in the job.
process.env.E2E_TELEMETRY_DISABLED ??= '1';

// An app that is already running (CI, a PR preview, staging). Without it, e2e starts the app itself.
// Never point goal tests at production: an agent clicks on its own and changes records.
const runningApp = process.env.E2E_BASE_URL;

export default {
  // One file per job document: e2e/goals/<job>.e2e.ts, plus the sign-in setup test.
  tests: ['e2e/goals/**/*.e2e.ts'],
  targets: [
    {
      name: 'web',
      engine: web({ viewport: { width: 1440, height: 1000 } }),
      app: runningApp
        ? { url: runningApp, identity: 'REPLACE-app-name', environment: 'staging' }
        : {
            url: 'http://127.0.0.1:0',
            // A stable identity keeps the replay cache valid when the port or preview URL changes.
            identity: 'REPLACE-app-name',
            command: {
              executable: 'npm',
              // REPLACE with the app's own start command. {port} is the free port e2e picks.
              args: ['run', 'dev', '--', '--port', '{port}'],
              env: { PORT: '{port}' },
              log: '.e2e/logs/app.log',
            },
          },
    },
  ],
  agents: {
    default: {
      // Vercel AI Gateway reads AI_GATEWAY_API_KEY. Change the model with E2E_MODEL, without a code edit.
      model: gateway(process.env.E2E_MODEL ?? 'anthropic/claude-sonnet-4.5'),
      // REPLACE with what the app calls things, and what the agent must never do.
      context: 'REPLACE: the app is ... Never delete real data, buy anything or send invitations.',
    },
  },
  // Committed recordings in .e2e/cache/. Read-write on a developer machine, read-only in CI.
  cache: { mode: process.env.CI ? 'read-only' : 'read-write', dir: '.e2e/cache' },
} satisfies E2EConfig;
