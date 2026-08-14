import { defineConfig, devices } from '@playwright/test'

// IDK-504: the measurement config, sibling to playwright.config.ts but for
// timing, not layout/behaviour assertions. Measurement must never contend
// with another measurement or be silently retried, so -- unlike the e2e
// config -- everything here runs serially and exactly once.
export default defineConfig({
  testDir: './tests/perf',
  testMatch: '**/*.perf.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'pnpm build && pnpm preview --host 127.0.0.1',
      port: 4173,
      reuseExistingServer: true,
    },
    {
      // The API server runs against the seeded perf dataset, not a scratch e2e
      // database: same alembic-upgrade-then-serve shape as playwright.config.ts,
      // seeding first when the dataset is not already there. dataset-shape.json is
      // the seeder's final output, so its presence is the "already seeded" marker.
      // `scripts/perf/run.mjs` deletes the whole perf-results/ directory before a
      // full run, which is what makes every run measure a freshly seeded dataset;
      // this webServer only fills in a missing one.
      command:
        'set -e; ' +
        'export YUNO_DATABASE_URL="sqlite+pysqlite:///$(pwd)/perf-results/perf.db"; ' +
        'mkdir -p "$(pwd)/perf-results"; ' +
        'uv run --directory server alembic upgrade head; ' +
        '[ -f "$(pwd)/perf-results/dataset-shape.json" ] || ' +
        'uv run --directory server python scripts/seed_performance_dataset.py ' +
        '--database-url "$YUNO_DATABASE_URL" --json-out "$(pwd)/perf-results/dataset-shape.json"; ' +
        'uv run --directory server uvicorn yuno.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/health',
      timeout: 120_000,
      reuseExistingServer: true,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
