/**
 * GET /api/setup-test
 * Creates a test invite code for local development
 * Only works in local development mode
 */

export async function onRequestGet(context) {
  const { env } = context;

  const testCode = {
    code: "TEST123",
    createdAt: new Date().toISOString(),
    maxUses: 100,
    usedCount: 0,
    active: true
  };

  await env.INVITE_CODES.put("TEST123", JSON.stringify(testCode));

  return new Response(JSON.stringify({
    success: true,
    message: "Test code TEST123 created",
    code: testCode
  }), {
    headers: { "Content-Type": "application/json" }
  });
}
