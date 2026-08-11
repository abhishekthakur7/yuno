import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'pnpm build && pnpm preview --host 127.0.0.1',
      port: 4173,
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'YUNO_DATABASE_URL="sqlite+pysqlite:///./.e2e.db" uv run --directory server alembic upgrade head && YUNO_DATABASE_URL="sqlite+pysqlite:///./.e2e.db" uv run --directory server uvicorn yuno.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/health',
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
