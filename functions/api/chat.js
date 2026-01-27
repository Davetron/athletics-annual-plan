/**
 * POST /api/chat
 * Proxies chat messages to Claude API
 */

// Rate limit configuration (in-memory, resets on cold start)
const rateLimits = new Map();
const RATE_LIMIT_WINDOW = 60 * 1000; // 1 minute
const RATE_LIMIT_MAX = 10; // requests per window

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const sessionId = request.headers.get('X-Session-ID');

    if (!sessionId) {
      return jsonResponse({ error: 'Session ID required' }, 401);
    }

    // Rate limiting
    const rateLimitResult = checkRateLimit(sessionId);
    if (!rateLimitResult.allowed) {
      return jsonResponse({
        error: 'Rate limit exceeded. Please wait a moment before trying again.'
      }, 429);
    }

    // Parse request
    const { system, messages } = await request.json();

    if (!messages || !Array.isArray(messages)) {
      return jsonResponse({ error: 'Messages array required' }, 400);
    }

    // Call Claude API
    const claudeResponse = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-3-5-haiku-20241022',
        max_tokens: 4096,
        system: system || '',
        messages: messages.map(m => ({
          role: m.role,
          content: m.content
        }))
      })
    });

    if (!claudeResponse.ok) {
      const errorText = await claudeResponse.text();
      console.error('Claude API error:', errorText);
      return jsonResponse({
        error: 'Failed to get response from AI'
      }, 502);
    }

    const data = await claudeResponse.json();

    return jsonResponse(data, 200);

  } catch (error) {
    console.error('Chat error:', error);
    return jsonResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * Simple in-memory rate limiter
 */
function checkRateLimit(sessionId) {
  const now = Date.now();
  const windowStart = now - RATE_LIMIT_WINDOW;

  // Get or create rate limit entry
  let entry = rateLimits.get(sessionId);

  if (!entry || entry.windowStart < windowStart) {
    entry = { windowStart: now, count: 0 };
  }

  entry.count++;
  rateLimits.set(sessionId, entry);

  // Clean up old entries periodically (every 100 requests)
  if (rateLimits.size > 100) {
    for (const [key, val] of rateLimits) {
      if (val.windowStart < windowStart) {
        rateLimits.delete(key);
      }
    }
  }

  return {
    allowed: entry.count <= RATE_LIMIT_MAX,
    remaining: Math.max(0, RATE_LIMIT_MAX - entry.count)
  };
}

function jsonResponse(data, status) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
    }
  });
}
