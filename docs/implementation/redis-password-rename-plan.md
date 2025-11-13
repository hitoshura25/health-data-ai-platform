# Implementation Plan: Redis Password Variable Rename

**Document Version**: 1.0
**Date**: 2025-01-13
**Status**: Ready for Implementation
**Estimated Time**: 30-45 minutes (including testing)

---

## Executive Summary

Rename `WEBAUTHN_REDIS_PASSWORD` to `HEALTH_REDIS_PASSWORD` across the codebase to accurately reflect its usage and prevent architectural confusion. The current naming incorrectly suggests the password is for the WebAuthn stack's Redis instance, when it's actually for the health services Redis instance.

---

## Background & Context

### Current Architecture

The platform uses **two separate Redis instances**:

1. **`webauthn-redis`** (port 6380) - WebAuthn Stack
   - Container: `webauthn-redis`
   - Password Source: Docker secret from `webauthn-stack/docker/secrets/redis_password`
   - Used By: WebAuthn server for session storage
   - Compose File: `webauthn-stack/docker/docker-compose.yml`

2. **`health-redis`** (port 6379) - Health Services Stack
   - Container: `health-redis`
   - Password Source: Environment variable `WEBAUTHN_REDIS_PASSWORD` (INCORRECT NAME)
   - Used By: Health API (rate limiting), Message Queue service
   - Compose File: `infrastructure/redis.compose.yml`

### Problem Statement

The variable name `WEBAUTHN_REDIS_PASSWORD` is **misleading** because:
- ❌ Implies it's for WebAuthn's Redis (port 6380), but it's not
- ❌ WebAuthn server never uses this variable (uses Docker secrets instead)
- ❌ Actually configures the health services Redis (port 6379)
- ❌ Comment in `redis.compose.yml` incorrectly states "webauthn-server (sessions)"
- ❌ Creates confusion for developers understanding the architecture

### Solution

Rename to `HEALTH_REDIS_PASSWORD` to:
- ✅ Match container name `health-redis`
- ✅ Align with naming conventions: `HEALTH_API_DB`, `DATALAKE_*`, `MQ_*`
- ✅ Clearly indicate it's for health services, not WebAuthn
- ✅ Prevent future architectural confusion

---

## Impact Analysis

### Files Affected (8 modifications across 4 files)

| File | Lines | Occurrences | Risk Level |
|------|-------|-------------|------------|
| `infrastructure/setup-secure-env.sh` | 31, 95 | 2 | **HIGH** - Generates .env |
| `infrastructure/redis.compose.yml` | 2, 11, 13 | 3 | **HIGH** - Redis config |
| `setup-all-services.sh` | 81, 90 | 2 | **MEDIUM** - Propagates to services |
| `services/health-api-service/health-api.compose.yml` | 19, 20 | 2 | **MEDIUM** - Service config |

### Services Impacted

- ✅ Health API Service (rate limiting)
- ✅ Message Queue Service (Redis storage)
- ✅ Data Lake Service (no impact - doesn't use Redis)
- ✅ WebAuthn Stack (no impact - uses separate Redis with Docker secrets)

### CI/CD Impact

- GitHub Actions workflow `.github/workflows/health_api_ci.yml` - **WILL BENEFIT** from this fix
- Current CI failure with Redis health check will be resolved by adding the export

---

## Detailed Implementation Steps

### Phase 1: Update Infrastructure Configuration (Critical Path)

#### Step 1.1: Update `infrastructure/setup-secure-env.sh`

**File**: `infrastructure/setup-secure-env.sh`

**Change 1 - Variable Generation (Line 31)**
```bash
# BEFORE:
WEBAUTHN_REDIS_PASSWORD=$(generate_long_secret)

# AFTER:
HEALTH_REDIS_PASSWORD=$(generate_long_secret)
```

**Change 2 - Message Queue URL (Line 95)**
```bash
# BEFORE:
MQ_REDIS_URL=redis://:${WEBAUTHN_REDIS_PASSWORD}@localhost:6379

# AFTER:
MQ_REDIS_URL=redis://:${HEALTH_REDIS_PASSWORD}@localhost:6379
```

**NEW - Add Missing Export (Insert after Line 57, in Redis section)**
```bash
# --- Redis Cache & Sessions ---
REDIS_PORT=6379
HEALTH_REDIS_PASSWORD=${HEALTH_REDIS_PASSWORD}  # <-- ADD THIS LINE
```

**Rationale**: This is the root source that generates all downstream .env files. Must be updated first.

---

#### Step 1.2: Update `infrastructure/redis.compose.yml`

**File**: `infrastructure/redis.compose.yml`

**Change 1 - Comment (Line 2)**
```yaml
# BEFORE:
# Used by: health-api-service (rate limiting), webauthn-server (sessions), message-queue

# AFTER:
# Used by: health-api-service (rate limiting), message-queue service
# Note: WebAuthn stack uses separate Redis (webauthn-redis on port 6380)
```

**Change 2 - Redis Command (Line 11)**
```yaml
# BEFORE:
    command: redis-server --appendonly yes --requirepass ${WEBAUTHN_REDIS_PASSWORD}

# AFTER:
    command: redis-server --appendonly yes --requirepass ${HEALTH_REDIS_PASSWORD}
```

**Change 3 - Health Check (Line 13)**
```yaml
# BEFORE:
      test: ["CMD", "redis-cli", "--pass", "${WEBAUTHN_REDIS_PASSWORD}", "ping"]

# AFTER:
      test: ["CMD", "redis-cli", "--pass", "${HEALTH_REDIS_PASSWORD}", "ping"]
```

**Rationale**: Direct Docker Compose configuration for the health Redis container.

---

### Phase 2: Update Service Propagation Scripts

#### Step 2.1: Update `setup-all-services.sh`

**File**: `setup-all-services.sh`

**Change 1 - Health API Redis URL (Line 81)**
```bash
# BEFORE:
REDIS_URL=redis://:${WEBAUTHN_REDIS_PASSWORD}@localhost:6379

# AFTER:
REDIS_URL=redis://:${HEALTH_REDIS_PASSWORD}@localhost:6379
```

**Change 2 - Rate Limiter Storage URI (Line 90)**
```bash
# BEFORE:
UPLOAD_RATE_LIMIT_STORAGE_URI=redis://:${WEBAUTHN_REDIS_PASSWORD}@localhost:6379

# AFTER:
UPLOAD_RATE_LIMIT_STORAGE_URI=redis://:${HEALTH_REDIS_PASSWORD}@localhost:6379
```

**Rationale**: This script propagates infrastructure credentials to service-specific .env files.

---

### Phase 3: Update Service Docker Compose Files

#### Step 3.1: Update `services/health-api-service/health-api.compose.yml`

**File**: `services/health-api-service/health-api.compose.yml`

**Change 1 - Redis URL Environment Variable (Line 19)**
```yaml
# BEFORE:
      - REDIS_URL=redis://:${WEBAUTHN_REDIS_PASSWORD}@redis:6379

# AFTER:
      - REDIS_URL=redis://:${HEALTH_REDIS_PASSWORD}@redis:6379
```

**Change 2 - Rate Limiter Storage URI (Line 20)**
```yaml
# BEFORE:
      - UPLOAD_RATE_LIMIT_STORAGE_URI=redis://:${WEBAUTHN_REDIS_PASSWORD}@redis:6379

# AFTER:
      - UPLOAD_RATE_LIMIT_STORAGE_URI=redis://:${HEALTH_REDIS_PASSWORD}@redis:6379
```

**Rationale**: Service runtime configuration that references the infrastructure Redis password.

---

## Implementation Sequence (CRITICAL - Follow Order)

**DO NOT skip steps or change order - dependencies exist between files.**

```bash
# Step 0: Backup current configuration
cp infrastructure/setup-secure-env.sh infrastructure/setup-secure-env.sh.backup
cp infrastructure/redis.compose.yml infrastructure/redis.compose.yml.backup
cp setup-all-services.sh setup-all-services.sh.backup
cp services/health-api-service/health-api.compose.yml services/health-api-service/health-api.compose.yml.backup

# Step 1: Update infrastructure scripts (MUST BE FIRST)
# Edit: infrastructure/setup-secure-env.sh (3 changes)
# - Line 31: Variable generation
# - Line 95: MQ_REDIS_URL
# - After Line 57: Add export HEALTH_REDIS_PASSWORD

# Step 2: Update Redis compose configuration
# Edit: infrastructure/redis.compose.yml (3 changes)
# - Line 2: Comment
# - Line 11: Command
# - Line 13: Health check

# Step 3: Regenerate all .env files
./setup-all-services.sh

# Step 4: Update service propagation script
# Edit: setup-all-services.sh (2 changes)
# - Line 81: REDIS_URL
# - Line 90: UPLOAD_RATE_LIMIT_STORAGE_URI

# Step 5: Update service compose file
# Edit: services/health-api-service/health-api.compose.yml (2 changes)
# - Line 19: REDIS_URL
# - Line 20: UPLOAD_RATE_LIMIT_STORAGE_URI

# Step 6: Regenerate .env files again (picks up changes from step 4-5)
./setup-all-services.sh
```

---

## Testing Strategy

### Test Phase 1: Environment Variable Generation

**Objective**: Verify .env files are correctly generated with new variable name

```bash
# 1. Regenerate all .env files
./setup-all-services.sh

# 2. Verify infrastructure .env
grep "HEALTH_REDIS_PASSWORD" infrastructure/.env
# Expected: HEALTH_REDIS_PASSWORD=<64-character-hex-string>

grep "WEBAUTHN_REDIS_PASSWORD" infrastructure/.env
# Expected: No matches (old variable removed)

# 3. Verify root .env (copied from infrastructure)
grep "HEALTH_REDIS_PASSWORD" .env
# Expected: HEALTH_REDIS_PASSWORD=<64-character-hex-string>

# 4. Verify health-api-service .env
grep "HEALTH_REDIS_PASSWORD" services/health-api-service/.env
# Expected: Found in REDIS_URL and UPLOAD_RATE_LIMIT_STORAGE_URI

# 5. Verify message-queue .env
grep "HEALTH_REDIS_PASSWORD" services/message-queue/.env
# Expected: Found in MQ_REDIS_URL
```

**Success Criteria**: ✅ All .env files contain `HEALTH_REDIS_PASSWORD`, none contain `WEBAUTHN_REDIS_PASSWORD`

---

### Test Phase 2: Docker Compose Validation

**Objective**: Ensure Docker Compose correctly substitutes environment variables

```bash
# 1. Stop all services
docker compose down -v

# 2. Start Redis only with new configuration
docker compose up -d redis

# 3. Check Redis container health
docker ps --filter "name=health-redis" --format "table {{.Names}}\t{{.Status}}"
# Expected: health-redis   Up X seconds (healthy)

# 4. Test Redis authentication with new password
REDIS_PASS=$(grep "HEALTH_REDIS_PASSWORD" .env | cut -d= -f2)
docker exec health-redis redis-cli --pass "$REDIS_PASS" ping
# Expected: PONG

# 5. Check for environment variable substitution errors
docker compose config | grep -i "webauthn_redis_password"
# Expected: No matches (old variable should not appear)

docker compose config | grep -i "health_redis_password"
# Expected: Multiple matches showing correct substitution
```

**Success Criteria**: ✅ Redis starts healthy, authentication works, no variable substitution errors

---

### Test Phase 3: Service Integration Tests

**Objective**: Verify health-api-service can connect to Redis with new credentials

```bash
# 1. Start all infrastructure services
docker compose up -d postgres redis minio rabbitmq

# 2. Wait for all services to be healthy (max 30 seconds)
timeout 30 bash -c 'until docker compose ps | grep -q "healthy"; do sleep 2; done'

# 3. Check all service health statuses
docker compose ps
# Expected: All services show "healthy" or "running"

# 4. Activate virtual environment
source .venv/bin/activate

# 5. Run health-api integration tests (tests Redis rate limiting)
cd services/health-api-service
export PYTHONPATH="${PWD}"
pytest tests/test_health_api_integration.py::test_health_ready_endpoint -v
# Expected: PASSED - validates Redis connection

pytest tests/test_health_api_integration.py::test_upload_rate_limiting -v
# Expected: PASSED - validates Redis rate limiting works

# 6. Run all health-api tests
pytest tests/ -v
# Expected: All 27 tests PASSED
```

**Success Criteria**: ✅ All integration tests pass, Redis rate limiting functional

---

### Test Phase 4: CI/CD Validation (GitHub Actions)

**Objective**: Verify GitHub Actions workflow succeeds with new variable name

```bash
# LOCAL SIMULATION (mimics CI environment):

# 1. Clean environment (simulate fresh CI runner)
docker compose down -v
rm -f .env infrastructure/.env services/*/\.env

# 2. Regenerate .env files (simulates CI step)
./setup-all-services.sh

# 3. Verify HEALTH_REDIS_PASSWORD is exported and available
source .env
echo "HEALTH_REDIS_PASSWORD: ${HEALTH_REDIS_PASSWORD:0:10}..." # Show first 10 chars
# Expected: Shows password prefix (confirms export worked)

# 4. Run the exact CI test command
source .venv/bin/activate
./run-tests.sh health-api -v -s
# Expected: All tests PASSED

# GITHUB ACTIONS:
# After merging, monitor workflow at:
# https://github.com/[your-repo]/actions/workflows/health_api_ci.yml
```

**Success Criteria**: ✅ Local simulation passes, GitHub Actions workflow succeeds

---

### Test Phase 5: WebAuthn Stack Isolation Verification

**Objective**: Confirm WebAuthn stack is unaffected (uses separate Redis)

```bash
# 1. Start WebAuthn stack
cd webauthn-stack/docker
docker compose up -d

# 2. Check WebAuthn Redis is using Docker secrets (not env vars)
docker inspect webauthn-redis | jq '.[0].Config.Cmd'
# Expected: Shows command using /run/secrets/redis_password

docker exec webauthn-redis ls -l /run/secrets/
# Expected: Shows redis_password file

# 3. Verify WebAuthn Redis password is different
WEBAUTHN_REDIS_SECRET=$(docker exec webauthn-redis cat /run/secrets/redis_password)
HEALTH_REDIS_PASS=$(grep "HEALTH_REDIS_PASSWORD" ../../.env | cut -d= -f2)

if [ "$WEBAUTHN_REDIS_SECRET" != "$HEALTH_REDIS_PASS" ]; then
  echo "✅ Passwords are different (correct isolation)"
else
  echo "❌ Passwords match (isolation broken!)"
fi

# 4. Run WebAuthn E2E tests
cd ..
npm test
# Expected: All WebAuthn tests pass

cd ../..
```

**Success Criteria**: ✅ WebAuthn uses separate credentials, all tests pass

---

## Rollback Plan

If issues occur during implementation, follow these steps:

### Immediate Rollback (< 5 minutes)

```bash
# 1. Stop all services
docker compose down -v

# 2. Restore backup files
cp infrastructure/setup-secure-env.sh.backup infrastructure/setup-secure-env.sh
cp infrastructure/redis.compose.yml.backup infrastructure/redis.compose.yml
cp setup-all-services.sh.backup setup-all-services.sh
cp services/health-api-service/health-api.compose.yml.backup services/health-api-service/health-api.compose.yml

# 3. Regenerate .env files with original configuration
./setup-all-services.sh

# 4. Restart services
docker compose up -d

# 5. Verify rollback successful
docker compose ps
source .venv/bin/activate
./run-tests.sh health-api -v
```

### Git Rollback (if changes committed)

```bash
# Find the commit before changes
git log --oneline -5

# Revert specific commit
git revert <commit-hash>

# Or reset to previous commit (if not pushed)
git reset --hard HEAD~1

# Regenerate .env and restart
./setup-all-services.sh
docker compose up -d
```

---

## Post-Implementation Verification Checklist

### Configuration Verification

- [ ] `infrastructure/.env` contains `HEALTH_REDIS_PASSWORD` (no `WEBAUTHN_REDIS_PASSWORD`)
- [ ] Root `.env` contains `HEALTH_REDIS_PASSWORD`
- [ ] `services/health-api-service/.env` uses `HEALTH_REDIS_PASSWORD` in URLs
- [ ] `services/message-queue/.env` uses `HEALTH_REDIS_PASSWORD` in URLs
- [ ] All backup files created before changes

### Docker Compose Verification

- [ ] `docker compose config` shows no `WEBAUTHN_REDIS_PASSWORD` references
- [ ] `docker compose config` shows correct `HEALTH_REDIS_PASSWORD` substitution
- [ ] Redis container starts healthy
- [ ] Redis authentication works with new password
- [ ] Health-api container starts and connects to Redis

### Testing Verification

- [ ] All 27 health-api integration tests pass
- [ ] Rate limiting tests pass (validates Redis connection)
- [ ] Message queue tests pass (if implemented)
- [ ] WebAuthn E2E tests pass (confirms isolation)
- [ ] GitHub Actions CI workflow succeeds

### Documentation Verification

- [ ] Comment in `redis.compose.yml` accurately describes usage
- [ ] No confusing references to "webauthn" for health services Redis
- [ ] Architecture clearly documented (two separate Redis instances)

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Tests fail after rename** | Medium | High | Run full test suite after each phase; rollback if failures |
| **CI/CD breaks** | Low | High | Test locally with same env setup as CI; monitor first CI run |
| **Services can't connect to Redis** | Low | High | Verify .env generation before starting services; check logs |
| **Variable not exported in .env** | Medium | Critical | Add explicit export line in setup-secure-env.sh (Phase 1) |
| **Confusion with WebAuthn Redis** | Low (after fix) | Low | Update comments to clearly distinguish the two Redis instances |

---

## Success Metrics

### Immediate (Day 0)

- ✅ All 4 files updated correctly
- ✅ All .env files regenerated with new variable
- ✅ All 27 health-api integration tests pass locally
- ✅ Docker Compose health checks pass for all services
- ✅ GitHub Actions CI workflow succeeds

### Short-term (Week 1)

- ✅ No regression issues reported
- ✅ Documentation reflects correct architecture
- ✅ Team understands two separate Redis instances

### Long-term (Month 1)

- ✅ No confusion about Redis credential usage
- ✅ New developers onboard with correct understanding
- ✅ Future services use correct naming conventions

---

## Additional Notes

### Naming Convention Alignment

After this change, all infrastructure credentials will follow a consistent pattern:

```bash
# Database credentials
POSTGRES_USER=...
POSTGRES_PASSWORD=...
HEALTH_API_DB=healthapi

# Redis credentials
HEALTH_REDIS_PASSWORD=...          # ← NEW (was WEBAUTHN_REDIS_PASSWORD)

# MinIO credentials
DATALAKE_MINIO_ACCESS_KEY=...
DATALAKE_MINIO_SECRET_KEY=...

# RabbitMQ credentials
MQ_RABBITMQ_USER=...
MQ_RABBITMQ_PASS=...

# Application secrets
SECRET_KEY=...
```

### Future Considerations

1. **If a third service needs Redis**: Use `health-redis` (port 6379) with `HEALTH_REDIS_PASSWORD`
2. **Database separation pattern**: Already follows this correctly (separate ports, separate DBs)
3. **Secret management**: Consider migrating to Docker secrets for health services (like WebAuthn) in production

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-13 | AI Assistant | Initial implementation plan |

---

## References

- **Redis Documentation**: Two separate instances for architectural isolation
- **Related Files**:
  - `CLAUDE.md` - Project architecture documentation
  - `webauthn-stack/docs/INTEGRATION.md` - WebAuthn integration guide
  - `.github/workflows/health_api_ci.yml` - CI workflow configuration

---

**READY FOR IMPLEMENTATION** ✅

Follow the implementation sequence exactly as documented. Run tests after each phase. Keep backups until all tests pass.
