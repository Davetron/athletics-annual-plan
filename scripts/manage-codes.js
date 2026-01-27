#!/usr/bin/env node

/**
 * CLI tool for managing invite codes
 *
 * Usage:
 *   npm run codes create SPRINT2025 --max-uses 10
 *   npm run codes list
 *   npm run codes deactivate SPRINT2025
 *   npm run codes info SPRINT2025
 *
 * Requires wrangler to be authenticated and KV namespace to be set up.
 */

import { execFileSync } from 'child_process';

const KV_NAMESPACE = 'INVITE_CODES';

// Parse command line arguments
const args = process.argv.slice(2);
const command = args[0];

async function main() {
  switch (command) {
    case 'create':
      await createCode(args[1], parseOptions(args.slice(2)));
      break;
    case 'list':
      await listCodes();
      break;
    case 'deactivate':
      await deactivateCode(args[1]);
      break;
    case 'activate':
      await activateCode(args[1]);
      break;
    case 'info':
      await getCodeInfo(args[1]);
      break;
    case 'delete':
      await deleteCode(args[1]);
      break;
    default:
      printUsage();
  }
}

/**
 * Create a new invite code
 */
async function createCode(code, options = {}) {
  if (!code) {
    console.error('Error: Code is required');
    console.log('Usage: npm run codes create <CODE> [--max-uses <number>]');
    process.exit(1);
  }

  const codeUpper = code.toUpperCase().trim();

  // Check if code already exists
  try {
    const existing = await kvGet(codeUpper);
    if (existing) {
      console.error(`Error: Code "${codeUpper}" already exists`);
      process.exit(1);
    }
  } catch (e) {
    // Code doesn't exist, which is what we want
  }

  const codeData = {
    code: codeUpper,
    createdAt: new Date().toISOString(),
    maxUses: options.maxUses || null,
    usedCount: 0,
    active: true
  };

  await kvPut(codeUpper, JSON.stringify(codeData));

  console.log(`\n✓ Created invite code: ${codeUpper}`);
  console.log(`  Max uses: ${codeData.maxUses || 'Unlimited'}`);
  console.log(`  Status: Active\n`);
}

/**
 * List all invite codes
 */
async function listCodes() {
  const keys = await kvList();

  if (!keys.length) {
    console.log('\nNo invite codes found.\n');
    return;
  }

  console.log('\n╔══════════════════════════════════════════════════════════════════╗');
  console.log('║                        INVITE CODES                              ║');
  console.log('╠══════════════════════════════════════════════════════════════════╣');
  console.log('║  Code           │ Uses    │ Max     │ Status     │ Last Used    ║');
  console.log('╟─────────────────┼─────────┼─────────┼────────────┼──────────────╢');

  for (const key of keys) {
    try {
      const data = await kvGet(key.name);
      if (data) {
        const codeData = JSON.parse(data);
        const codeDisplay = codeData.code.padEnd(15);
        const used = String(codeData.usedCount || 0).padEnd(7);
        const max = (codeData.maxUses || '∞').toString().padEnd(7);
        const status = (codeData.active ? 'Active' : 'Inactive').padEnd(10);
        const lastUsed = codeData.lastUsed
          ? new Date(codeData.lastUsed).toLocaleDateString()
          : 'Never';

        console.log(`║  ${codeDisplay} │ ${used} │ ${max} │ ${status} │ ${lastUsed.padEnd(12)} ║`);
      }
    } catch (e) {
      console.log(`║  ${key.name.padEnd(15)} │ Error reading data                          ║`);
    }
  }

  console.log('╚══════════════════════════════════════════════════════════════════╝\n');
}

/**
 * Deactivate a code
 */
async function deactivateCode(code) {
  if (!code) {
    console.error('Error: Code is required');
    process.exit(1);
  }

  const codeUpper = code.toUpperCase().trim();
  const data = await kvGet(codeUpper);

  if (!data) {
    console.error(`Error: Code "${codeUpper}" not found`);
    process.exit(1);
  }

  const codeData = JSON.parse(data);
  codeData.active = false;
  codeData.deactivatedAt = new Date().toISOString();

  await kvPut(codeUpper, JSON.stringify(codeData));
  console.log(`\n✓ Deactivated code: ${codeUpper}\n`);
}

/**
 * Activate a code
 */
async function activateCode(code) {
  if (!code) {
    console.error('Error: Code is required');
    process.exit(1);
  }

  const codeUpper = code.toUpperCase().trim();
  const data = await kvGet(codeUpper);

  if (!data) {
    console.error(`Error: Code "${codeUpper}" not found`);
    process.exit(1);
  }

  const codeData = JSON.parse(data);
  codeData.active = true;
  delete codeData.deactivatedAt;

  await kvPut(codeUpper, JSON.stringify(codeData));
  console.log(`\n✓ Activated code: ${codeUpper}\n`);
}

/**
 * Get detailed info about a code
 */
async function getCodeInfo(code) {
  if (!code) {
    console.error('Error: Code is required');
    process.exit(1);
  }

  const codeUpper = code.toUpperCase().trim();
  const data = await kvGet(codeUpper);

  if (!data) {
    console.error(`Error: Code "${codeUpper}" not found`);
    process.exit(1);
  }

  const codeData = JSON.parse(data);

  console.log(`\n╔════════════════════════════════════════╗`);
  console.log(`║  Invite Code: ${codeData.code.padEnd(24)}║`);
  console.log(`╠════════════════════════════════════════╣`);
  console.log(`║  Status:      ${(codeData.active ? 'Active' : 'Inactive').padEnd(24)}║`);
  console.log(`║  Created:     ${new Date(codeData.createdAt).toLocaleString().padEnd(24)}║`);
  console.log(`║  Uses:        ${codeData.usedCount.toString().padEnd(24)}║`);
  console.log(`║  Max Uses:    ${(codeData.maxUses || 'Unlimited').toString().padEnd(24)}║`);
  if (codeData.lastUsed) {
    console.log(`║  Last Used:   ${new Date(codeData.lastUsed).toLocaleString().padEnd(24)}║`);
  }
  if (codeData.deactivatedAt) {
    console.log(`║  Deactivated: ${new Date(codeData.deactivatedAt).toLocaleString().padEnd(24)}║`);
  }
  console.log(`╚════════════════════════════════════════╝\n`);
}

/**
 * Delete a code
 */
async function deleteCode(code) {
  if (!code) {
    console.error('Error: Code is required');
    process.exit(1);
  }

  const codeUpper = code.toUpperCase().trim();

  await kvDelete(codeUpper);
  console.log(`\n✓ Deleted code: ${codeUpper}\n`);
}

/**
 * Parse command line options
 */
function parseOptions(args) {
  const options = {};

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--max-uses' && args[i + 1]) {
      options.maxUses = parseInt(args[i + 1], 10);
      i++;
    }
  }

  return options;
}

/**
 * Print usage information
 */
function printUsage() {
  console.log(`
╔══════════════════════════════════════════════════════════════╗
║            ATHLETICS ANNUAL PLAN - CODE MANAGER              ║
╚══════════════════════════════════════════════════════════════╝

Usage:
  npm run codes <command> [options]

Commands:
  create <CODE> [--max-uses <n>]   Create a new invite code
  list                             List all invite codes
  info <CODE>                      Show details for a code
  activate <CODE>                  Activate a deactivated code
  deactivate <CODE>                Deactivate a code
  delete <CODE>                    Permanently delete a code

Examples:
  npm run codes create SPRINT2025
  npm run codes create CLUB2025 --max-uses 50
  npm run codes list
  npm run codes info SPRINT2025
  npm run codes deactivate OLDCODE

Note: Requires wrangler to be authenticated.
  Run 'npx wrangler login' if not already logged in.
`);
}

// KV helper functions using wrangler CLI with execFileSync for safety
function kvGet(key) {
  try {
    // Use execFileSync with arguments array to prevent shell injection
    const result = execFileSync(
      'npx',
      ['wrangler', 'kv:key', 'get', `--binding=${KV_NAMESPACE}`, key],
      { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
    );
    return result.trim();
  } catch (e) {
    return null;
  }
}

function kvPut(key, value) {
  // Use execFileSync with arguments array to prevent shell injection
  execFileSync(
    'npx',
    ['wrangler', 'kv:key', 'put', `--binding=${KV_NAMESPACE}`, key, value],
    { encoding: 'utf-8' }
  );
}

function kvDelete(key) {
  // Use execFileSync with arguments array to prevent shell injection
  execFileSync(
    'npx',
    ['wrangler', 'kv:key', 'delete', `--binding=${KV_NAMESPACE}`, key, '--force'],
    { encoding: 'utf-8' }
  );
}

function kvList() {
  try {
    // Use execFileSync with arguments array to prevent shell injection
    const result = execFileSync(
      'npx',
      ['wrangler', 'kv:key', 'list', `--binding=${KV_NAMESPACE}`],
      { encoding: 'utf-8' }
    );
    return JSON.parse(result);
  } catch (e) {
    return [];
  }
}

// Run
main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
