/**
 * POST /api/validate-code
 * Validates invite codes against KV store
 */

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const { code } = await request.json();

    if (!code) {
      return jsonResponse({ valid: false, error: 'Code is required' }, 400);
    }

    const codeUpper = code.toUpperCase().trim();

    // Look up code in KV
    const codeData = await env.INVITE_CODES.get(codeUpper, { type: 'json' });

    if (!codeData) {
      return jsonResponse({ valid: false, error: 'Invalid invite code' }, 401);
    }

    // Check if code is active
    if (!codeData.active) {
      return jsonResponse({ valid: false, error: 'This code has been deactivated' }, 401);
    }

    // Check usage limit
    if (codeData.maxUses && codeData.usedCount >= codeData.maxUses) {
      return jsonResponse({ valid: false, error: 'This code has reached its usage limit' }, 401);
    }

    // Increment usage count
    codeData.usedCount = (codeData.usedCount || 0) + 1;
    codeData.lastUsed = new Date().toISOString();

    await env.INVITE_CODES.put(codeUpper, JSON.stringify(codeData));

    // Generate session ID
    const sessionId = crypto.randomUUID();

    return jsonResponse({
      valid: true,
      sessionId,
      remainingUses: codeData.maxUses ? codeData.maxUses - codeData.usedCount : null
    }, 200);

  } catch (error) {
    console.error('Validate code error:', error);
    return jsonResponse({ error: 'Internal server error' }, 500);
  }
}

function jsonResponse(data, status) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
    }
  });
}
