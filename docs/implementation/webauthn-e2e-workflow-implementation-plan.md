# WebAuthn E2E Workflow - Detailed Implementation Plan

**Document Version**: 1.0
**Date**: 2025-01-13
**Status**: Ready for Implementation
**Estimated Time**: 45-60 minutes (implementation + testing)

---

## Executive Summary

Create a GitHub Actions CI workflow (`.github/workflows/webauthn_ci.yml`) to automate end-to-end Playwright tests for the webauthn-stack. This workflow will follow the exact setup process documented in `webauthn-stack/README.md` and leverage existing scripts where possible.

**Key Insight**: The webauthn-stack is **independent** from the health services stack. It has its own Docker Compose configuration in `webauthn-stack/docker/` and does not use `setup-all-services.sh`.

---

## Background & Context

### Current Testing Setup (Local)

According to `webauthn-stack/README.md`, the manual testing process is:

```bash
# 1. Generate Docker secrets (manual)
cd webauthn-stack/docker
openssl rand -base64 32 | cut -c1-32 > secrets/postgres_password
openssl rand -base64 32 | cut -c1-32 > secrets/redis_password
openssl rand -base64 32 | cut -c1-32 > secrets/jwt_master_key

# 2. Verify secrets
bash setup-secrets.sh  # Validates secrets exist

# 3. Start Docker stack
docker compose up -d

# 4. Build and test client
cd ..  # Back to webauthn-stack root
npm install
npm run build
npm test  # Runs Playwright E2E tests
```

### Test Suite Overview

**Test Files** (4 total in `webauthn-stack/tests/`):
1. `webauthn.spec.js` - Basic registration and authentication flows
2. `jwt-verification.spec.js` - JWT token validation and protected endpoints
3. `jwt-key-rotation.spec.js` - **Long-running** (~2 minutes per test, 4 tests total)
4. `health-upload-e2e.spec.js` - Integration with health API upload

**Global Setup/Teardown**:
- `global-setup.js` - Automatically starts test client (`npm start` on port 8082)
- `global-teardown.js` - Cleans up test client process

**Playwright Configuration** (`playwright.config.js`):
- CI optimizations enabled (`process.env.CI`)
- Retries: 2 on CI
- Workers: 2 parallel on CI
- Max failures: 1 (fail fast)
- Artifacts: screenshots, videos, traces on failure

---

## Comparison with Existing Workflows

### Health API Workflow (Reference)

```yaml
# .github/workflows/health_api_ci.yml
steps:
  - Checkout
  - Setup Python 3.11
  - Generate .env files (./setup-all-services.sh)
  - Install Python dependencies
  - Run tests (./run-tests.sh health-api)
```

### Data Lake Workflow (Reference)

```yaml
# .github/workflows/data_lake_ci.yml
steps:
  - Checkout
  - Setup Python 3.11
  - Generate .env files (./setup-all-services.sh)
  - Install Python dependencies
  - Run tests (./run-tests.sh data-lake)
```

### WebAuthn Workflow (New - This Plan)

```yaml
# .github/workflows/webauthn_ci.yml
steps:
  - Checkout
  - Setup Node.js 20.x (with npm cache)
  - Generate Docker secrets (3 files)
  - Start Docker Compose services
  - Wait for services (health check)
  - Install npm dependencies
  - Build TypeScript client
  - Install Playwright browsers
  - Run Playwright E2E tests
  - Upload artifacts (reports, videos)
  - Cleanup (always: stop Docker)
```

**Key Differences**:
- ✅ Node.js instead of Python
- ✅ Docker secrets as **files** (not env vars)
- ✅ Browser installation required (Playwright)
- ✅ Longer timeout (20 min) due to key rotation tests
- ✅ Independent of `setup-all-services.sh`

---

## Critical Fixes from Gemini Spec Review

### Issue #1: Secret Handling (CRITICAL FIX)

**Gemini spec said (WRONG)**:
```yaml
- name: Generate Secrets
  run: |
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)" >> $GITHUB_ENV
```

**Correct implementation** (file-based Docker secrets):
```yaml
- name: Generate Docker Secrets
  run: |
    mkdir -p webauthn-stack/docker/secrets
    openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/postgres_password
    openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/redis_password
    openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/jwt_master_key
```

**Why**: Docker Compose config uses `secrets.file` mounts, not environment variables.

---

### Issue #2: Health Check Endpoint (FIX)

**Gemini spec said**: `http://localhost:8080/health`
**Correct endpoint**: `http://localhost:8000/health` (Envoy Gateway)

**Verification** (from `global-setup.js:87`):
```javascript
await waitForService('http://localhost:8000/health', 'WebAuthn server', 30000);
```

---

### Issue #3: Missing Playwright Browser Installation (CRITICAL)

**Gemini spec**: Completely omitted this step
**Required addition**: `npx playwright install --with-deps chromium`

**Why**: GitHub Actions runners don't have Chromium pre-installed. Tests will fail with "No browser found" error without this step.

---

### Issue #4: Timeout Configuration (ADJUSTMENT)

**Gemini spec**: 15 minutes job, 5 minutes test step
**Recommended**: 20 minutes job, 5 minutes test step

**Reasoning**:
- JWT key rotation tests: 4 tests × ~2 min each = ~8 minutes
- Service startup: ~60 seconds
- Build + install: ~2-3 minutes
- Buffer for CI variability: ~5 minutes
- **Total**: ~16-17 minutes typical, 20 minute buffer appropriate

---

### Issue #5: Docker Compose Command (MODERNIZATION)

**Gemini spec**: `docker-compose` (deprecated syntax)
**Modern syntax**: `docker compose` (Docker CLI, matches other workflows)

---

## Detailed Implementation Steps

### Step 1: Create Workflow File

**File**: `.github/workflows/webauthn_ci.yml`

```yaml
name: WebAuthn Stack CI

on:
  push:
    branches: [ "main" ]
    paths:
      - 'webauthn-stack/**'
  pull_request:
    branches: [ "main" ]
    paths:
      - 'webauthn-stack/**'

permissions:
  contents: read

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 20

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'webauthn-stack/package-lock.json'

      - name: Generate Docker Secrets
        run: |
          mkdir -p webauthn-stack/docker/secrets
          openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/postgres_password
          openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/redis_password
          openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/jwt_master_key
          echo "✅ Docker secrets generated"

      - name: Verify Secrets
        working-directory: webauthn-stack/docker
        run: |
          bash setup-secrets.sh

      - name: Start Docker Services
        working-directory: webauthn-stack/docker
        run: |
          docker compose up -d
          echo "✅ Docker services started"

      - name: Wait for Services to be Ready
        run: |
          echo "⏳ Waiting for WebAuthn server to be ready..."
          timeout=120  # 2 minutes
          elapsed=0
          interval=2

          while [ $elapsed -lt $timeout ]; do
            if curl -f -s http://localhost:8000/health > /dev/null; then
              echo "✅ WebAuthn server is ready (${elapsed}s)"
              exit 0
            fi
            echo "⏳ Waiting... (${elapsed}s)"
            sleep $interval
            elapsed=$((elapsed + interval))
          done

          echo "❌ WebAuthn server failed to become ready after ${timeout}s"
          docker compose -f webauthn-stack/docker/docker-compose.yml logs
          exit 1

      - name: Install Dependencies
        working-directory: webauthn-stack
        run: |
          npm ci
          echo "✅ Dependencies installed"

      - name: Build TypeScript Client
        working-directory: webauthn-stack
        run: |
          npm run build
          echo "✅ TypeScript client built"

      - name: Install Playwright Browsers
        working-directory: webauthn-stack
        run: |
          npx playwright install --with-deps chromium
          echo "✅ Playwright browsers installed"

      - name: Run Playwright E2E Tests
        working-directory: webauthn-stack
        timeout-minutes: 10
        env:
          CI: true
        run: |
          npm test

      - name: Upload Test Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: webauthn-stack/playwright-report/
          retention-days: 7

      - name: Upload Test Results (Screenshots, Videos)
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: webauthn-stack/test-results/
          retention-days: 7

      - name: Stop Docker Services
        if: always()
        working-directory: webauthn-stack/docker
        run: |
          docker compose down -v
          echo "✅ Docker services stopped and cleaned up"
```

---

## Implementation Breakdown

### Section 1: Workflow Metadata

```yaml
name: WebAuthn Stack CI

on:
  push:
    branches: [ "main" ]
    paths:
      - 'webauthn-stack/**'
  pull_request:
    branches: [ "main" ]
    paths:
      - 'webauthn-stack/**'
```

**Rationale**:
- Only triggers when webauthn-stack files change
- Matches pattern from health_api_ci.yml and data_lake_ci.yml
- Prevents unnecessary runs when unrelated files change

---

### Section 2: Job Configuration

```yaml
jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 20
```

**Rationale**:
- 20 minutes accommodates long JWT key rotation tests
- ubuntu-latest matches other workflows
- Prevents runaway jobs from consuming excessive resources

---

### Section 3: Node.js Setup with Caching

```yaml
- name: Set up Node.js
  uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'
    cache-dependency-path: 'webauthn-stack/package-lock.json'
```

**Rationale**:
- Node.js 20 matches package.json requirements
- npm cache significantly speeds up subsequent runs
- Cache key based on package-lock.json hash ensures fresh install when dependencies change

**Performance Impact**:
- First run: ~2-3 minutes for npm install
- Cached runs: ~15-30 seconds for npm install

---

### Section 4: Docker Secrets Generation

```yaml
- name: Generate Docker Secrets
  run: |
    mkdir -p webauthn-stack/docker/secrets
    openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/postgres_password
    openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/redis_password
    openssl rand -base64 32 | cut -c1-32 > webauthn-stack/docker/secrets/jwt_master_key
    echo "✅ Docker secrets generated"
```

**Why this approach**:
1. **File-based secrets**: Docker Compose mounts these as `/run/secrets/*` in containers
2. **Follows README**: Exact commands from `webauthn-stack/README.md` lines 48-51
3. **Secure randomness**: `openssl rand` provides cryptographically secure random bytes
4. **No git commits**: Secrets directory is gitignored, ephemeral in CI

**Alternative approaches (rejected)**:
- ❌ Environment variables: WebAuthn server expects file-based secrets
- ❌ GitHub Secrets: Unnecessary for ephemeral CI runs
- ❌ External KMS: Overkill for CI testing

---

### Section 5: Secret Verification

```yaml
- name: Verify Secrets
  working-directory: webauthn-stack/docker
  run: |
    bash setup-secrets.sh
```

**Rationale**:
- Reuses existing `setup-secrets.sh` validation script
- Ensures all 3 required secrets are present
- Fails early if secret generation had issues
- Matches developer local workflow

**What setup-secrets.sh does**:
- ✅ Checks `secrets/postgres_password` exists
- ✅ Checks `secrets/redis_password` exists
- ✅ Checks `secrets/jwt_master_key` exists
- ✅ Validates file permissions (warns if too permissive)
- ❌ Exits with code 1 if any secret missing

---

### Section 6: Start Docker Services

```yaml
- name: Start Docker Services
  working-directory: webauthn-stack/docker
  run: |
    docker compose up -d
    echo "✅ Docker services started"
```

**Services Started** (from `docker-compose.yml`):
1. **postgres** (port 5433) - Credential storage
2. **redis** (port 6380) - Session cache
3. **webauthn-server** - FIDO2 + JWT issuer
4. **envoy-gateway** (port 8000) - Public entry point
5. **example-service** - Protected API demo
6. **example-service-sidecar** - mTLS proxy
7. **jaeger** (port 16687) - Distributed tracing

**Startup Order** (orchestrated by Docker Compose):
1. postgres, redis start
2. webauthn-server waits for postgres + redis health checks
3. envoy-gateway waits for webauthn-server
4. All services start in parallel where dependencies allow

**Flags**:
- `-d`: Detached mode (runs in background)
- No `--build`: Uses pre-built images (faster for CI)

---

### Section 7: Health Check Wait Loop

```yaml
- name: Wait for Services to be Ready
  run: |
    echo "⏳ Waiting for WebAuthn server to be ready..."
    timeout=120  # 2 minutes
    elapsed=0
    interval=2

    while [ $elapsed -lt $timeout ]; do
      if curl -f -s http://localhost:8000/health > /dev/null; then
        echo "✅ WebAuthn server is ready (${elapsed}s)"
        exit 0
      fi
      echo "⏳ Waiting... (${elapsed}s)"
      sleep $interval
      elapsed=$((elapsed + interval))
    done

    echo "❌ WebAuthn server failed to become ready after ${timeout}s"
    docker compose -f webauthn-stack/docker/docker-compose.yml logs
    exit 1
```

**Rationale**:
- **Endpoint**: `http://localhost:8000/health` (Envoy Gateway)
- **Timeout**: 2 minutes (generous for CI environment)
- **Interval**: 2 seconds (responsive polling)
- **Failure handling**: Dumps Docker logs for debugging

**Why not use `docker compose wait`**:
- Not all services have health checks defined
- HTTP health check is more reliable indicator of readiness

**Expected startup time**:
- Local: ~15-30 seconds
- CI (first run): ~30-60 seconds
- CI (cached): ~20-40 seconds

---

### Section 8: Install Dependencies

```yaml
- name: Install Dependencies
  working-directory: webauthn-stack
  run: |
    npm ci
    echo "✅ Dependencies installed"
```

**Why `npm ci` instead of `npm install`**:
- ✅ Faster in CI (uses package-lock.json directly)
- ✅ Deterministic installs (reproducible builds)
- ✅ Removes existing node_modules first (clean install)
- ✅ Fails if package-lock.json is out of sync

**Dependencies installed** (from `package.json`):
- TypeScript compiler
- Webpack (bundler)
- Playwright (E2E testing)
- Express (dev server)
- SimpleWebAuthn browser library
- Other dev dependencies

---

### Section 9: Build TypeScript Client

```yaml
- name: Build TypeScript Client
  working-directory: webauthn-stack
  run: |
    npm run build
    echo "✅ TypeScript client built"
```

**What `npm run build` does** (from `package.json:11`):
```json
"build": "NODE_ENV=production webpack && npm run build:server"
```

**Build steps**:
1. Webpack: Bundles TypeScript client → `dist/umd/webauthn-client.umd.js`
2. TypeScript: Compiles server → `dist/src/server.js`

**Output artifacts** (required for tests):
- `dist/umd/` - Bundled client library (loaded by test client)
- `dist/src/` - Compiled Express server (serves test UI)
- `public/` - Static HTML (copied to dist)

**Build time**:
- Typical: 20-40 seconds
- CI: 30-60 seconds (varies with runner load)

---

### Section 10: Install Playwright Browsers (CRITICAL)

```yaml
- name: Install Playwright Browsers
  working-directory: webauthn-stack
  run: |
    npx playwright install --with-deps chromium
    echo "✅ Playwright browsers installed"
```

**Why this is CRITICAL**:
- GitHub Actions runners don't have Chromium pre-installed
- Tests will fail with "No browser found" error without this step
- `--with-deps` installs system dependencies (libgbm, fonts, etc.)

**What gets installed**:
- Chromium browser (~300 MB)
- System libraries: libgbm1, libxshmfence1, etc.
- Font packages for proper rendering

**Performance**:
- First time: ~30-60 seconds (downloads browser)
- Playwright caches browsers in `~/.cache/ms-playwright`
- Subsequent runs: ~5-10 seconds (validates cache)

**Why only Chromium**:
- Playwright config specifies 2 projects: `chromium` and `Mobile Chrome`
- Both use Chromium engine
- No Firefox or Webkit needed for this test suite

---

### Section 11: Run Playwright E2E Tests

```yaml
- name: Run Playwright E2E Tests
  working-directory: webauthn-stack
  timeout-minutes: 10
  env:
    CI: true
  run: |
    npm test
```

**What `npm test` does** (from `package.json:17`):
```json
"test": "playwright test"
```

**Playwright CI Optimizations** (from `playwright.config.js`):
- Retries: 2 (flaky test tolerance)
- Workers: 2 (parallel execution)
- Max failures: 1 (fail fast)
- Forbid `.only`: Prevents accidental test isolation

**Test execution flow**:
1. **Global setup** (`global-setup.js`):
   - Starts test client: `npm start` (port 8082)
   - Waits for test client health check
   - Waits for WebAuthn server health check

2. **Test suites** (4 files, run in parallel):
   - `webauthn.spec.js` - Registration/auth flows (~1 min)
   - `jwt-verification.spec.js` - Token validation (~1 min)
   - `jwt-key-rotation.spec.js` - **Long** (~8 min, 4 tests)
   - `health-upload-e2e.spec.js` - Upload integration (~1 min)

3. **Global teardown** (`global-teardown.js`):
   - Kills test client process
   - Cleanup temporary files

**Expected duration**:
- Typical: 8-10 minutes (key rotation tests dominate)
- Fast: 6-8 minutes (all tests pass quickly)
- Slow: 10-12 minutes (retries on failures)

**Timeout reasoning**:
- 10 minutes for test step (generous buffer for retries)
- 20 minutes for overall job (includes setup)

---

### Section 12: Upload Artifacts (Always)

```yaml
- name: Upload Test Report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: webauthn-stack/playwright-report/
    retention-days: 7
```

**What's in playwright-report**:
- HTML test report (interactive UI)
- Test results JSON
- Test summary
- Execution timeline

**Why `if: always()`**:
- Upload even on success (good for record-keeping)
- Upload on failure (essential for debugging)
- Upload on cancellation (partial results useful)

**Retention**: 7 days (balances storage cost vs usefulness)

---

### Section 13: Upload Artifacts (On Failure)

```yaml
- name: Upload Test Results (Screenshots, Videos)
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: test-results
    path: webauthn-stack/test-results/
    retention-days: 7
```

**What's in test-results** (only captured on failure):
- Screenshots (captured at failure point)
- Videos (full test recording)
- Traces (Playwright Inspector format)
- HAR files (network logs)

**Playwright auto-capture** (from `playwright.config.js`):
- `screenshot: 'only-on-failure'`
- `video: { mode: 'retain-on-failure' }`
- `trace: 'on-first-retry'`

**Why `if: failure()` only**:
- Videos/screenshots expensive (storage)
- Only needed for debugging failures
- Report (previous step) sufficient for successes

---

### Section 14: Cleanup (Always)

```yaml
- name: Stop Docker Services
  if: always()
  working-directory: webauthn-stack/docker
  run: |
    docker compose down -v
    echo "✅ Docker services stopped and cleaned up"
```

**Why `if: always()`**:
- Cleanup even on test failure
- Cleanup on workflow cancellation
- Prevents resource leaks on shared runners

**Flags**:
- `down`: Stop and remove containers
- `-v`: Remove volumes (clean slate for next run)

**What gets cleaned**:
- All 7 service containers
- Named volumes: `webauthn_postgres_data`, `webauthn_redis_data`
- Network: `webauthn-stack_default`
- Secrets remain (gitignored, will be regenerated next run)

---

## Testing Strategy

### Pre-Implementation Checklist

- [ ] Review existing workflows (health_api_ci.yml, data_lake_ci.yml)
- [ ] Understand webauthn-stack README setup process
- [ ] Verify webauthn-stack tests run locally
- [ ] Check Docker Compose services start successfully
- [ ] Confirm Playwright config has CI optimizations

### Implementation Testing

**Phase 1: Syntax Validation**
```bash
# Validate workflow YAML syntax
yamllint .github/workflows/webauthn_ci.yml

# Check for common issues
actionlint .github/workflows/webauthn_ci.yml
```

**Phase 2: Local Simulation**
```bash
# Simulate CI environment locally
cd webauthn-stack

# 1. Generate secrets (as CI would)
mkdir -p docker/secrets
openssl rand -base64 32 | cut -c1-32 > docker/secrets/postgres_password
openssl rand -base64 32 | cut -c1-32 > docker/secrets/redis_password
openssl rand -base64 32 | cut -c1-32 > docker/secrets/jwt_master_key

# 2. Verify secrets
cd docker && bash setup-secrets.sh

# 3. Start services
docker compose up -d

# 4. Wait for health
curl -f http://localhost:8000/health

# 5. Install, build, test
cd ..
npm ci
npm run build
npx playwright install --with-deps chromium
CI=true npm test

# 6. Cleanup
cd docker && docker compose down -v
```

**Phase 3: Trigger Workflow on Branch**
```bash
# Create test branch
git checkout -b test/webauthn-ci

# Make trivial change to webauthn-stack
echo "# CI test" >> webauthn-stack/README.md

# Commit and push
git add .github/workflows/webauthn_ci.yml webauthn-stack/README.md
git commit -m "test: add WebAuthn CI workflow"
git push origin test/webauthn-ci

# Monitor at: https://github.com/[repo]/actions
```

**Phase 4: Verify Artifacts**
- ✅ Test report uploaded (HTML viewable)
- ✅ Test results uploaded on failure (screenshots, videos)
- ✅ Logs show all 4 test files executed
- ✅ Cleanup occurred (no lingering containers)

---

## Success Criteria

### Must-Have (Critical)

- [ ] All 4 test suites pass consistently
- [ ] JWT key rotation tests complete (~8 minutes)
- [ ] Docker services start and health checks pass
- [ ] Playwright browsers install successfully
- [ ] Artifacts uploaded on failure (screenshots, videos)
- [ ] Cleanup always occurs (no resource leaks)

### Should-Have (Important)

- [ ] Workflow completes in < 15 minutes (typical)
- [ ] npm cache speeds up subsequent runs
- [ ] Logs are readable and helpful for debugging
- [ ] Workflow only triggers on webauthn-stack changes

### Nice-to-Have (Optional)

- [ ] Parallel test execution (2 workers)
- [ ] Test report viewable in GitHub UI
- [ ] Retry on flaky tests (up to 2 retries)

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Playwright browser install fails** | Low | High | Use `--with-deps` flag; pre-install system packages if needed |
| **Docker services timeout** | Medium | High | 2-minute health check; dump logs on failure for debugging |
| **JWT key rotation tests timeout** | Low | Medium | 10-minute test timeout; 20-minute job timeout |
| **npm cache corruption** | Very Low | Medium | Use `npm ci` (clean install); cache busting on failure |
| **Flaky tests** | Medium | Low | 2 retries configured in Playwright config |
| **Resource leaks (containers)** | Very Low | Medium | `if: always()` cleanup step; `-v` flag removes volumes |

---

## Comparison: Gemini Spec vs. This Plan

| Aspect | Gemini Spec | This Plan | Status |
|--------|-------------|-----------|--------|
| **Secret handling** | Env vars (`$GITHUB_ENV`) | File-based (`secrets/`) | ✅ **FIXED** |
| **Health endpoint** | `localhost:8080` | `localhost:8000` | ✅ **FIXED** |
| **Browser install** | ❌ Missing | `playwright install --with-deps` | ✅ **ADDED** |
| **Timeout** | 15 min job | 20 min job, 10 min test | ✅ **ADJUSTED** |
| **Docker command** | `docker-compose` | `docker compose` | ✅ **MODERNIZED** |
| **Leverages scripts** | ❌ No | `setup-secrets.sh` | ✅ **IMPROVED** |
| **Follows README** | ❌ No | Exact process | ✅ **IMPROVED** |

---

## Post-Implementation Validation

### Workflow Health Checks

**After first successful run**:
1. Review workflow execution time (should be < 15 min typical)
2. Check npm cache hit rate (should be > 90% after first run)
3. Verify all 4 test files executed
4. Confirm artifacts uploaded correctly

**Weekly monitoring**:
- Average execution time (watch for drift)
- Failure rate (should be < 5%)
- Flaky test patterns (retries needed?)

### Troubleshooting Guide

**Symptom**: Tests fail with "No browser found"
**Cause**: Playwright browser not installed
**Fix**: Ensure `playwright install --with-deps chromium` step ran

**Symptom**: Health check timeout (2 minutes)
**Cause**: Docker services failed to start
**Fix**: Check Docker logs in workflow output; verify secrets generated

**Symptom**: JWT key rotation tests timeout
**Cause**: Tests take ~2 min each, 4 tests total
**Fix**: Increase test timeout to 10 minutes (already in plan)

**Symptom**: npm install slow (> 2 minutes)
**Cause**: npm cache miss
**Fix**: Verify `cache-dependency-path` in setup-node step

---

## Additional Considerations

### Future Enhancements

1. **Parallel test execution**: Already configured (2 workers)
2. **Test result comments on PR**: Use `actions/github-script` to post results
3. **Performance benchmarking**: Track test execution times over time
4. **Browser matrix**: Add Firefox/Webkit if needed (currently Chromium-only)

### Integration with Other Workflows

This workflow is **independent** from:
- `health_api_ci.yml` (Python-based, health services)
- `data_lake_ci.yml` (Python-based, data lake services)
- `message_queue_ci.yml` (Python-based, message queue services)

**No conflicts** expected as:
- Uses different technology stack (Node.js vs Python)
- Uses different port ranges (8000, 5433, 6380 vs 5432, 6379, 9000)
- Triggers on different path patterns (`webauthn-stack/**` vs `services/**`)

### Cost Optimization

**GitHub Actions free tier**:
- 2,000 minutes/month (free for public repos)
- This workflow: ~15 minutes per run
- **Budget**: ~130 runs/month

**Optimization strategies**:
1. Path filtering (already implemented) - prevents unnecessary runs
2. npm cache (already implemented) - reduces install time
3. Fail fast (already configured) - stops early on failures
4. Artifact retention: 7 days (balances cost vs usefulness)

---

## Documentation Updates

### Files to Update

1. **`webauthn-stack/README.md`**:
   - Add "Continuous Integration" section
   - Link to workflow file
   - Badge: `[![WebAuthn CI](https://github.com/[repo]/actions/workflows/webauthn_ci.yml/badge.svg)](https://github.com/[repo]/actions/workflows/webauthn_ci.yml)`

2. **Root `README.md`** (if exists):
   - Add WebAuthn CI to list of workflows
   - Show status badge

3. **`CLAUDE.md`**:
   - Update CI/CD section with new workflow
   - Add to testing infrastructure documentation

---

## Final Checklist

### Pre-Commit

- [ ] Workflow YAML syntax valid
- [ ] All step names descriptive and clear
- [ ] Secret generation uses file-based approach
- [ ] Health check uses correct endpoint (`localhost:8000`)
- [ ] Playwright browser installation included
- [ ] Timeouts appropriate (20 min job, 10 min test)
- [ ] Cleanup step has `if: always()`
- [ ] Artifact uploads configured

### Post-Merge

- [ ] Monitor first workflow run
- [ ] Verify all tests pass
- [ ] Check execution time (< 15 min)
- [ ] Validate artifacts uploaded
- [ ] Confirm cleanup occurred
- [ ] Update documentation with badge

---

## Appendix A: Complete Workflow File

See **Step 1: Create Workflow File** above for the complete YAML definition.

---

## Appendix B: Local Testing Commands

```bash
# Full CI simulation (run from repo root)
cd webauthn-stack

# Setup
mkdir -p docker/secrets
openssl rand -base64 32 | cut -c1-32 > docker/secrets/postgres_password
openssl rand -base64 32 | cut -c1-32 > docker/secrets/redis_password
openssl rand -base64 32 | cut -c1-32 > docker/secrets/jwt_master_key

cd docker && bash setup-secrets.sh && cd ..

# Services
cd docker && docker compose up -d && cd ..

# Wait
while ! curl -f -s http://localhost:8000/health > /dev/null; do sleep 2; done

# Build & Test
npm ci
npm run build
npx playwright install --with-deps chromium
CI=true npm test

# Cleanup
cd docker && docker compose down -v && cd ..
```

---

## Appendix C: Workflow Comparison Table

| Feature | Health API | Data Lake | WebAuthn (New) |
|---------|------------|-----------|----------------|
| **Language** | Python 3.11 | Python 3.11 | Node.js 20 |
| **Test Framework** | pytest | pytest | Playwright |
| **Setup Script** | `setup-all-services.sh` | `setup-all-services.sh` | Manual secrets |
| **Docker Services** | All health services | MinIO only | WebAuthn stack |
| **Test Duration** | ~2 min | ~1 min | ~10 min |
| **Artifacts** | None | None | Reports + videos |
| **Caching** | None | None | npm cache |
| **Timeout** | Default (360 min) | Default (360 min) | 20 min |

---

**READY FOR IMPLEMENTATION** ✅

Follow the implementation steps exactly as documented. Run local simulation first, then create workflow file and trigger on test branch.
