const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/browser', workers: 1,
  use: { baseURL: 'http://127.0.0.1:18765', browserName: 'chromium' },
  webServer: { command: 'python3 scripts/browser_fixture.py', url: 'http://127.0.0.1:18765', reuseExistingServer: false },
});
