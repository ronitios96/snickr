const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { chromium } = require("playwright");

const baseURL = process.env.SNICKR_URL || "http://127.0.0.1:5001";
const repoRoot = path.resolve(__dirname, "../..");
const resultDir = path.join(repoRoot, "test-results", "playwright");
const resultPath = path.join(repoRoot, "report", "demo", "regression_result.json");
const defaultViewport = { width: 1440, height: 960 };

fs.mkdirSync(resultDir, { recursive: true });

function runCommand(command, args) {
  const result = spawnSync(command, args, {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed\n${result.stdout || ""}${result.stderr || ""}`.trim(),
    );
  }
}

function resetDatabase() {
  runCommand("psql", ["-d", "snickr_dev", "-v", "ON_ERROR_STOP=1", "-f", "schema.sql"]);
  runCommand("psql", ["-d", "snickr_dev", "-v", "ON_ERROR_STOP=1", "-f", "seed.sql"]);
}

function slugify(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

async function expectBody(page, pattern) {
  const text = await page.locator("body").innerText();
  assert.match(text, pattern);
  return text;
}

async function login(page, username, password = "password123") {
  await page.goto(baseURL, { waitUntil: "networkidle" });
  await page.locator("form.login-form input[name=identifier]").fill(username);
  await page.locator("form.login-form input[name=password]").fill(password);
  await page.locator("form.login-form button[type=submit]").click();
  await page.waitForURL("**/dashboard");
  await expectBody(page, new RegExp(`@${username}\\b`));
}

async function withPage(browser, testName, callback, options = {}) {
  const context = await browser.newContext({
    viewport: options.viewport || defaultViewport,
  });
  const page = await context.newPage();
  const browserIssues = [];

  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      browserIssues.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => browserIssues.push(`pageerror: ${error.message}`));

  try {
    await callback({ page, context });
    const unexpectedIssues = browserIssues.filter((issue) => {
      return !(options.allowedBrowserIssuePatterns || []).some((pattern) => pattern.test(issue));
    });
    assert.deepEqual(unexpectedIssues, [], `${testName} browser issues:\n${unexpectedIssues.join("\n")}`);
  } catch (error) {
    const screenshot = path.join(resultDir, `${slugify(testName)}-failure.png`);
    await page.screenshot({ path: screenshot, fullPage: false }).catch(() => {});
    error.message = `${error.message}\nFailure screenshot: ${screenshot}`;
    throw error;
  } finally {
    await context.close();
  }
}

const tests = [
  {
    name: "unauthenticated users are redirected to login",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        const response = await page.goto(`${baseURL}/dashboard`, { waitUntil: "networkidle" });
        assert.equal(response.status(), 200);
        assert.equal(new URL(page.url()).pathname, "/");
        await expectBody(page, /Sign in with a seeded account/i);
      });
    },
  },
  {
    name: "Aarav dashboard renders seeded workspaces",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "aarav");
        await expectBody(page, /FinPlex-Engineering/);
        await expectBody(page, /Lotus-RWA/);
        assert.equal(await page.locator("a.workspace-row").count(), 2);
      });
    },
  },
  {
    name: "channel posting writes through the backend",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "aarav");
        await page.goto(`${baseURL}/channels/1`, { waitUntil: "networkidle" });
        const body = `Regression post ${Date.now()}: demo posting is stable.`;
        await page.locator("textarea[name=body]").fill(body);
        await page.locator("form.composer button[type=submit]").click();
        await page.waitForLoadState("networkidle");
        await expectBody(page, new RegExp(body.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
      });
    },
  },
  {
    name: "search results are scoped by channel membership",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "aarav");
        await page.goto(`${baseURL}/search?q=perpendicular`, { waitUntil: "networkidle" });
        const text = await expectBody(page, /perpendicular/i);
        assert.equal(await page.locator(".result-row").count(), 2);
        assert.match(text, /#engineering/);
        assert.match(text, /#hiring/);
      });

      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "rohan");
        await page.goto(`${baseURL}/search?q=perpendicular`, { waitUntil: "networkidle" });
        const text = await expectBody(page, /perpendicular/i);
        assert.equal(await page.locator(".result-row").count(), 1);
        assert.match(text, /#engineering/);
        assert.doesNotMatch(text, /#hiring/);
      });
    },
  },
  {
    name: "Kavya can accept the seeded releases channel invitation",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "kavya");
        await expectBody(page, /#releases/);
        await page.locator("form[action*='/channel-invitations/'][action$='/accept'] button").first().click();
        await page.waitForURL("**/channels/2");
        await expectBody(page, /#releases/);
        await expectBody(page, /\bkavya\b/);
        await page.goto(`${baseURL}/dashboard`, { waitUntil: "networkidle" });
        await expectBody(page, /No pending channel invitations/);
      });
    },
  },
  {
    name: "non-members cannot open or post to private channels",
    async run(browser) {
      await withPage(browser, this.name, async ({ page, context }) => {
        await login(page, "rohan");
        const pageResponse = await page.goto(`${baseURL}/channels/3`, { waitUntil: "networkidle" });
        assert.equal(pageResponse.status(), 403);
        await expectBody(page, /Not allowed/);

        const postResponse = await context.request.post(`${baseURL}/channels/3/messages`, {
          form: { body: "This write should be blocked by membership checks." },
        });
        assert.equal(postResponse.status(), 403);
      }, { allowedBrowserIssuePatterns: [/403 \(FORBIDDEN\)/] });
    },
  },
  {
    name: "direct channel membership is enforced separately from workspace membership",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "aarav");
        const response = await page.goto(`${baseURL}/channels/6`, { waitUntil: "networkidle" });
        assert.equal(response.status(), 403);
        await expectBody(page, /Not allowed/);
      }, { allowedBrowserIssuePatterns: [/403 \(FORBIDDEN\)/] });
    },
  },
  {
    name: "workspace creation redirects to the new workspace",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "aarav");
        const name = `Regression Review Room ${Date.now()}`;
        await page.locator("form[action='/workspaces'] input[name=name]").fill(name);
        await page
          .locator("form[action='/workspaces'] textarea[name=description]")
          .fill("Created by the repeatable Playwright demo regression suite.");
        await page.locator("form[action='/workspaces'] button[type=submit]").click();
        await page.waitForLoadState("networkidle");
        assert.match(page.url(), /\/workspaces\/\d+$/);
        await expectBody(page, new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
        await expectBody(page, /Workspace admin/i);
      });
    },
  },
  {
    name: "message bodies are escaped instead of executed",
    async run(browser) {
      await withPage(browser, this.name, async ({ page }) => {
        await login(page, "aarav");
        await page.goto(`${baseURL}/channels/1`, { waitUntil: "networkidle" });
        const marker = `SNICKR_ESCAPE_${Date.now()}`;
        const payload = `<script>window.__snickrXssFlag = true</script><strong>${marker}</strong>`;
        await page.locator("textarea[name=body]").fill(payload);
        await page.locator("form.composer button[type=submit]").click();
        await page.waitForLoadState("networkidle");
        await expectBody(page, new RegExp(marker));
        assert.equal(await page.evaluate(() => window.__snickrXssFlag === true), false);
        assert.equal(await page.locator("strong", { hasText: marker }).count(), 0);
      });
    },
  },
  {
    name: "mobile dashboard has no horizontal overflow",
    async run(browser) {
      await withPage(
        browser,
        this.name,
        async ({ page }) => {
          await login(page, "aarav");
          await expectBody(page, /Workspaces/);
          const metrics = await page.evaluate(() => ({
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
            bodyScrollWidth: document.body.scrollWidth,
          }));
          assert.ok(
            metrics.scrollWidth <= metrics.clientWidth + 2,
            `mobile overflow detected: ${JSON.stringify(metrics)}`,
          );
        },
        { viewport: { width: 390, height: 844 } },
      );
    },
  },
];

async function main() {
  const startedAt = new Date();
  const browser = await chromium.launch({ headless: true });
  const results = [];

  try {
    for (const testCase of tests) {
      const started = Date.now();
      process.stdout.write(`Running ${testCase.name} ... `);
      resetDatabase();
      try {
        await testCase.run(browser);
        const durationMs = Date.now() - started;
        results.push({ name: testCase.name, status: "passed", durationMs });
        console.log(`passed (${durationMs} ms)`);
      } catch (error) {
        const durationMs = Date.now() - started;
        results.push({
          name: testCase.name,
          status: "failed",
          durationMs,
          error: error.stack || error.message,
        });
        console.log(`failed (${durationMs} ms)`);
        throw error;
      }
    }
  } finally {
    await browser.close();
    resetDatabase();
    const summary = {
      baseURL,
      generatedAt: new Date().toISOString(),
      durationMs: new Date() - startedAt,
      passed: results.filter((result) => result.status === "passed").length,
      failed: results.filter((result) => result.status === "failed").length,
      results,
    };
    fs.writeFileSync(resultPath, `${JSON.stringify(summary, null, 2)}\n`);
  }

  console.log(`All ${tests.length} Playwright regression tests passed.`);
  console.log(`Wrote ${path.relative(repoRoot, resultPath)}.`);
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
