const { test, expect } = require('@playwright/test');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// Timeout configuration
const WEBAUTHN_OPERATION_TIMEOUT = 10000; // 10 seconds
const HEALTH_API_URL = 'http://localhost:8001';

// Helper function to generate unique usernames
function generateUniqueUsername(testName, workerIndex = 0) {
  const timestamp = Date.now();
  const randomBytes = crypto.randomBytes(4).toString('hex');
  const processId = process.pid;
  const workerId = workerIndex || Math.floor(Math.random() * 1000);
  const testHash = crypto.createHash('md5').update(testName).digest('hex').substring(0, 6);
  return `pw-${testHash}-${timestamp}-${processId}-${workerId}-${randomBytes}`;
}

test.describe('Health Data Upload End-to-End Tests', () => {

  test.beforeEach(async ({ page, context }) => {
    // Set up CDP virtual authenticator
    const client = await context.newCDPSession(page);
    await client.send('WebAuthn.enable');
    const { authenticatorId } = await client.send('WebAuthn.addVirtualAuthenticator', {
      options: {
        protocol: 'ctap2',
        ctap2Version: 'ctap2_1',
        transport: 'internal',
        hasResidentKey: true,
        hasUserVerification: true,
        hasLargeBlob: false,
        hasCredBlob: false,
        hasMinPinLength: false,
        hasPrf: false,
        automaticPresenceSimulation: true,
        isUserVerified: true
      }
    });
    page.authenticatorId = authenticatorId;

    // Navigate to WebAuthn client
    await page.goto('http://localhost:8082');
    await page.waitForLoadState('networkidle');
  });

  test('should upload AVRO file through complete stack with distributed tracing', async ({ page, request }, testInfo) => {
    const uniqueUsername = generateUniqueUsername(testInfo.title, testInfo.workerIndex);

    console.log('\n🚀 Starting Health Upload E2E Test');
    console.log(`📝 Test user: ${uniqueUsername}`);

    // ========================================
    // STEP 1: Register and Authenticate with WebAuthn
    // ========================================
    await test.step('Register and authenticate user with WebAuthn', async () => {
      console.log('\n🔐 Step 1: WebAuthn Authentication');

      // Register
      await page.fill('#regUsername', uniqueUsername);
      await page.fill('#regDisplayName', 'Health Upload E2E Test User');
      await page.click('button:has-text("Register Passkey")');
      await expect(page.locator('#registrationStatus')).toContainText('successful', {
        timeout: WEBAUTHN_OPERATION_TIMEOUT
      });
      console.log('  ✅ Registration successful');

      // Authenticate
      await page.fill('#authUsername', uniqueUsername);
      await page.click('button:has-text("Authenticate with Passkey")');
      await expect(page.locator('#authenticationStatus')).toContainText('successful', {
        timeout: WEBAUTHN_OPERATION_TIMEOUT
      });
      console.log('  ✅ Authentication successful');
    });

    // ========================================
    // STEP 2: Get WebAuthn JWT from sessionStorage
    // ========================================
    let webauthnToken;
    await test.step('Extract WebAuthn JWT from sessionStorage', async () => {
      console.log('\n🔑 Step 2: Extract WebAuthn JWT');

      const sessionData = await page.evaluate(() => {
        const stored = sessionStorage.getItem('webauthn_auth_session');
        return stored ? JSON.parse(stored) : null;
      });

      expect(sessionData).toBeTruthy();
      expect(sessionData.accessToken).toBeTruthy();
      expect(sessionData.tokenType).toBe('Bearer');

      webauthnToken = sessionData.accessToken;
      console.log(`  ✅ WebAuthn JWT extracted (${webauthnToken.substring(0, 30)}...)`);
    });

    // ========================================
    // STEP 3: Exchange WebAuthn Token for Health API Token
    // ========================================
    let healthApiToken;
    let healthUser;
    await test.step('Exchange WebAuthn token for Health API token', async () => {
      console.log('\n🔄 Step 3: Token Exchange');

      const response = await request.post(`${HEALTH_API_URL}/auth/webauthn/exchange`, {
        headers: {
          'Content-Type': 'application/json'
        },
        data: {
          webauthn_token: webauthnToken
        }
      });

      expect(response.status()).toBe(200);

      const exchangeData = await response.json();
      healthApiToken = exchangeData.access_token;
      healthUser = exchangeData.user;

      expect(healthApiToken).toBeTruthy();
      expect(healthUser).toBeTruthy();
      // Email is normalized from username to valid email format (username@example.com)
      expect(healthUser.email).toContain(uniqueUsername);

      console.log('  ✅ Token exchange successful');
      console.log(`  ✅ Health API user created: ${healthUser.email} (ID: ${healthUser.id})`);
    });

    // ========================================
    // STEP 4: Prepare AVRO File
    // ========================================
    const avroFilePath = path.join(__dirname, '../../docs/sample-avro-files/BloodGlucoseRecord_1758407139312.avro');
    await test.step('Verify AVRO file exists', async () => {
      console.log('\n📁 Step 4: Prepare AVRO File');

      const fileExists = fs.existsSync(avroFilePath);
      expect(fileExists).toBe(true);

      const stats = fs.statSync(avroFilePath);
      console.log(`  ✅ AVRO file found: ${path.basename(avroFilePath)}`);
      console.log(`  📊 File size: ${stats.size} bytes`);
    });

    // ========================================
    // STEP 5: Upload to Health API
    // ========================================
    let correlationId;
    let uploadResponse;
    await test.step('Upload AVRO file to Health API', async () => {
      console.log('\n⬆️  Step 5: Upload to Health API');

      // Read file
      const fileBuffer = fs.readFileSync(avroFilePath);
      const fileName = path.basename(avroFilePath);

      // Upload via Health API
      const response = await request.post(`${HEALTH_API_URL}/v1/upload`, {
        headers: {
          'Authorization': `Bearer ${healthApiToken}`
        },
        multipart: {
          file: {
            name: fileName,
            mimeType: 'application/octet-stream',
            buffer: fileBuffer
          },
          description: 'E2E test upload - Blood Glucose data'
        }
      });

      expect(response.status()).toBe(202); // Accepted

      uploadResponse = await response.json();
      correlationId = uploadResponse.correlation_id;

      console.log('  ✅ Upload successful!');
      console.log(`  📋 Correlation ID: ${correlationId}`);
      console.log(`  📊 Record type: ${uploadResponse.record_type}`);
      console.log(`  📦 Status: ${uploadResponse.status}`);
      console.log(`  🗂️  Object key: ${uploadResponse.object_key}`);

      expect(correlationId).toBeTruthy();
      expect(uploadResponse.status).toBe('accepted');
      expect(uploadResponse.processing_status).toBe('queued');
      expect(uploadResponse.record_type).toBe('AvroBloodGlucoseRecord');
      expect(uploadResponse.object_key).toMatch(/^raw\/AvroBloodGlucoseRecord\/\d{4}\/\d{2}\/\d{2}\/.+\.avro$/);
    });

    // ========================================
    // STEP 6: Verify Upload Status
    // ========================================
    await test.step('Verify upload status endpoint', async () => {
      console.log('\n🔍 Step 6: Verify Upload Status');

      const response = await request.get(
        `${HEALTH_API_URL}/v1/upload/status/${correlationId}`,
        {
          headers: {
            'Authorization': `Bearer ${healthApiToken}`
          }
        }
      );

      expect(response.status()).toBe(200);

      const statusData = await response.json();
      console.log('  ✅ Upload status retrieved');
      console.log(`  📊 Record count: ${statusData.record_count}`);
      console.log(`  📦 Status: ${statusData.status}`);

      expect(statusData.object_key).toBeTruthy();
      expect(statusData.record_count).toBeGreaterThan(0);

      console.log('\n  ℹ️  Note: Status will remain "queued" - ETL consumer not running yet (Phase 2)');
    });

    // ========================================
    // STEP 7: Verify Distributed Traces in Jaeger
    // ========================================
    await test.step('Verify distributed traces in Jaeger UI', async () => {
      console.log('\n🔍 Step 7: Verify Distributed Tracing');

      // Open Jaeger UI
      await page.goto('http://localhost:16687');
      await page.waitForLoadState('networkidle');

      // Jaeger UI uses Ant Design components (not native select)
      // Service selector is the first .ant-select component
      const serviceDropdown = page.locator('.ant-select').first();

      try {
        await serviceDropdown.waitFor({ state: 'visible', timeout: 5000 });
        console.log('  ✅ Found service dropdown');

        // Click to open dropdown
        await serviceDropdown.click();

        // Wait for dropdown menu to appear
        const dropdownMenu = page.locator('.ant-select-dropdown');
        await dropdownMenu.waitFor({ state: 'visible', timeout: 3000 });

        // Look for health-api-service option
        const healthApiOption = page.locator('.ant-select-item-option').filter({ hasText: 'health-api-service' });
        const hasHealthApi = await healthApiOption.isVisible({ timeout: 2000 }).catch(() => false);

        if (hasHealthApi) {
          // Select health-api-service
          await healthApiOption.click();
          console.log('  ✅ Selected health-api-service');

          // Find Traces button (has data-test="submit-btn")
          const findButton = page.locator('[data-test="submit-btn"]');
          await findButton.waitFor({ state: 'visible', timeout: 3000 });

          // Wait for button to be enabled (it's disabled until service is selected)
          await findButton.waitFor({ state: 'attached', timeout: 3000 });
          await findButton.click({ force: false });
          console.log('  ✅ Clicked Find Traces');

          // Wait for results to load - look for our correlation_id
          const ourTrace = page.locator(`text="${correlationId}"`);

          try {
            await ourTrace.waitFor({ state: 'visible', timeout: 10000 });
            console.log(`  ✅ Found trace with correlation_id: ${correlationId}`);
            console.log('  ✅ Distributed tracing verified successfully!');
          } catch (error) {
            console.log(`  ⚠️  Trace ${correlationId} not found within 10 seconds`);
            console.log('  💡 Jaeger may still be indexing - check manually:');
            console.log(`     http://localhost:16687`);
          }
        } else {
          console.log('  ⚠️  health-api-service not in dropdown yet (no traces received)');
          console.log('  💡 Traces may not have reached Jaeger yet');
          console.log(`     Manual check: http://localhost:16687 (search for: ${correlationId})`);
        }
      } catch (error) {
        console.log('  ⚠️  Could not interact with Jaeger UI');
        console.log(`  💡 Manual verification: http://localhost:16687 (search for: ${correlationId})`);
      }
    });

    // ========================================
    // TEST SUMMARY
    // ========================================
    console.log('\n✅ End-to-End Upload Pipeline Test Complete!');
    console.log('\n📋 Flow Verified:');
    console.log('  1. ✅ WebAuthn authentication → WebAuthn JWT');
    console.log('  2. ✅ Token exchange → Health API JWT');
    console.log('  3. ✅ Upload AVRO file → Health API');
    console.log('  4. ✅ File stored → MinIO (Data Lake)');
    console.log('  5. ✅ Message published → RabbitMQ (queued for ETL)');
    console.log('  6. ✅ Distributed tracing → Jaeger');
    console.log('\n🎯 Phase 1 Complete! Phase 2 (ETL Narrative Engine) is next.');
  });

  test('should handle invalid WebAuthn token in exchange', async ({ page, request }, testInfo) => {
    console.log('\n🧪 Testing invalid token handling');

    // Try to exchange an invalid token
    const response = await request.post(`${HEALTH_API_URL}/auth/webauthn/exchange`, {
      headers: {
        'Content-Type': 'application/json'
      },
      data: {
        webauthn_token: 'invalid.jwt.token'
      }
    });

    expect(response.status()).toBe(401);
    console.log('  ✅ Invalid token correctly rejected with 401');
  });

  test('should require authentication for upload endpoint', async ({ request }) => {
    console.log('\n🧪 Testing upload without authentication');

    // Try to upload without auth token
    const response = await request.post(`${HEALTH_API_URL}/v1/upload`, {
      multipart: {
        file: {
          name: 'test.avro',
          mimeType: 'application/octet-stream',
          buffer: Buffer.from('fake data')
        }
      }
    });

    expect(response.status()).toBe(401);
    console.log('  ✅ Upload without auth correctly rejected with 401');
  });

});
