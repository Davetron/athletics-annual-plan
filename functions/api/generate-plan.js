/**
 * POST /api/generate-plan
 * Uses Claude tool_use to generate a structured annual training plan
 * This guarantees proper JSON output format
 */

// Rate limit configuration
const rateLimits = new Map();
const RATE_LIMIT_WINDOW = 60 * 1000; // 1 minute
const RATE_LIMIT_MAX = 5; // requests per window (lower for generation)

// Tool definition for structured plan output
const GENERATE_PLAN_TOOL = {
  name: "generate_annual_plan",
  description: "Generate a complete 52-week periodized training plan for an athlete or squad. Call this tool with the full plan data.",
  input_schema: {
    type: "object",
    required: ["athlete", "season", "eventGroup", "periodization", "seasonStart", "competitions", "weeks"],
    properties: {
      athlete: {
        type: "string",
        description: "Name of athlete or squad"
      },
      season: {
        type: "string",
        description: "Season year range, e.g., '2025/2026'"
      },
      eventGroup: {
        type: "string",
        description: "Event category: sprints, long-sprints, middle-distance, endurance, hurdles, jumps, throws, multi-events"
      },
      periodization: {
        type: "string",
        enum: ["bi-phase", "single-peak"],
        description: "Periodization approach"
      },
      seasonStart: {
        type: "string",
        description: "ISO date of week 1 Monday (typically late August/early September)"
      },
      competitions: {
        type: "array",
        description: "List of target competitions",
        items: {
          type: "object",
          required: ["name", "date", "weekNum", "importance"],
          properties: {
            name: { type: "string", description: "Competition name" },
            date: { type: "string", description: "ISO date of competition" },
            weekNum: { type: "integer", minimum: 1, maximum: 52, description: "Week number (1-52)" },
            importance: { type: "integer", enum: [1, 2, 3], description: "1=major, 2=moderate, 3=minor" }
          }
        }
      },
      weeks: {
        type: "array",
        description: "All 52 weeks of the training plan",
        minItems: 52,
        maxItems: 52,
        items: {
          type: "object",
          required: ["weekNum", "startDate", "month", "phase", "phaseType", "load"],
          properties: {
            weekNum: { type: "integer", minimum: 1, maximum: 52 },
            startDate: { type: "string", description: "ISO date (Monday of that week)" },
            month: { type: "string", description: "Display month, e.g., 'Sep 25'" },
            phase: { type: "string", description: "Training phase name" },
            phaseType: {
              type: "string",
              enum: ["general-prep", "special-prep", "competition", "taper"],
              description: "Phase category for visualization"
            },
            block: { type: "string", description: "Training block name" },
            load: { type: "integer", minimum: 0, maximum: 4, description: "Training load 0-4" },
            competitions: {
              type: "array",
              items: { type: "string" },
              description: "Competition names this week"
            },
            competitionImportance: {
              type: ["integer", "null"],
              description: "Importance of competition this week (1-3) or null"
            },
            technical: { type: "string", description: "Technical focus for the week" },
            physical: { type: "string", description: "Physical development focus" }
          }
        }
      }
    }
  }
};

// System prompt for plan generation (focused on creating the plan)
const GENERATION_SYSTEM_PROMPT = `You are an expert athletics coach generating a 52-week periodized annual training plan.

Based on the conversation and athlete information provided, generate a complete plan using the generate_annual_plan tool.

## Periodization Guidelines

### Bi-Phase Season (Indoor + Outdoor)
- Weeks 1-3: Transition (end of previous season recovery)
- Weeks 4-14: General Prep I (base building, aerobic, strength)
- Weeks 15-18: Special Prep I (speed development, indoor specific)
- Weeks 19-27: Competition I - Indoor season
- Weeks 28: Transition
- Weeks 29-33: General Prep II (outdoor base)
- Weeks 34-37: Special Prep II (outdoor specific)
- Weeks 38-45: Competition II - Outdoor season
- Weeks 46-52: End of Season / Transition

### Single-Peak Season
- Weeks 1-3: Transition
- Weeks 4-18: General Prep (extended base)
- Weeks 19-28: Special Prep (progressive specificity)
- Weeks 29-45: Competition (peak maintenance)
- Weeks 46-52: Transition / Recovery

### Load Patterns
- Build progressively within blocks (2 → 3 → 4 → 2 deload)
- Reduce 1-2 weeks before major competitions
- Competition weeks: load 1-2
- Post-competition recovery: load 1-2
- Avoid consecutive max load (4) weeks

### Phase Characteristics
- General Prep: High volume, lower intensity, aerobic base, general strength
- Special Prep: Increasing intensity, event-specific conditioning, speed development
- Competition: Low volume, high intensity, race-specific work, recovery emphasis
- Taper: Minimal training, recovery focus

## Important Dates
- Season typically starts last Monday of August
- Indoor season: January-March
- Outdoor season: May-August

IMPORTANT: You must call the generate_annual_plan tool with the complete plan. Do not output JSON directly.`;

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
        error: 'Rate limit exceeded. Please wait before generating another plan.'
      }, 429);
    }

    // Parse request
    const { formData, messages } = await request.json();

    if (!formData) {
      return jsonResponse({ error: 'Form data required' }, 400);
    }

    // Build context message from form data and conversation
    const contextMessage = buildContextMessage(formData, messages || []);

    // Call Claude API with tool_use
    const claudeResponse = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': env.CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01'
      },
      body: JSON.stringify({
        model: 'claude-3-5-haiku-20241022',
        max_tokens: 8192,
        system: GENERATION_SYSTEM_PROMPT,
        tools: [GENERATE_PLAN_TOOL],
        tool_choice: { type: "tool", name: "generate_annual_plan" },
        messages: [{
          role: 'user',
          content: contextMessage
        }]
      })
    });

    if (!claudeResponse.ok) {
      const errorText = await claudeResponse.text();
      console.error('Claude API error:', errorText);
      return jsonResponse({
        error: 'Failed to generate plan. Please try again.'
      }, 502);
    }

    const data = await claudeResponse.json();

    // Extract the tool use result
    const toolUse = data.content?.find(block => block.type === 'tool_use');

    if (!toolUse || toolUse.name !== 'generate_annual_plan') {
      console.error('No tool use in response:', JSON.stringify(data.content));
      return jsonResponse({
        error: 'Failed to generate structured plan. Please try again.'
      }, 500);
    }

    // The plan is in toolUse.input
    const plan = toolUse.input;

    // Validate basic structure
    if (!plan.weeks || plan.weeks.length !== 52) {
      console.error('Invalid plan structure:', plan.weeks?.length);
      return jsonResponse({
        error: 'Generated plan was incomplete. Please try again.'
      }, 500);
    }

    return jsonResponse({
      success: true,
      plan: plan
    }, 200);

  } catch (error) {
    console.error('Generate plan error:', error);
    return jsonResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * Build context message from form data and conversation history
 */
function buildContextMessage(formData, messages) {
  let context = `Generate a 52-week annual training plan with the following details:

**Athlete/Squad:** ${formData.athleteName}
**Event Group:** ${formData.eventGroup}
**Season:** ${formData.season}
**Periodization:** ${formData.periodization === 'bi-phase' ? 'Bi-phase (indoor + outdoor peaks)' : 'Single-peak'}
**Target Competitions:** ${formData.targetCompetitions || 'Not specified'}
`;

  // Add relevant conversation context if any
  if (messages.length > 0) {
    context += `\n## Conversation Context\n`;
    for (const msg of messages) {
      const role = msg.role === 'user' ? 'User' : 'Coach';
      context += `${role}: ${msg.content}\n\n`;
    }
  }

  context += `\nNow generate the complete 52-week plan using the generate_annual_plan tool.`;

  return context;
}

/**
 * Simple in-memory rate limiter
 */
function checkRateLimit(sessionId) {
  const now = Date.now();
  const windowStart = now - RATE_LIMIT_WINDOW;

  let entry = rateLimits.get(sessionId);

  if (!entry || entry.windowStart < windowStart) {
    entry = { windowStart: now, count: 0 };
  }

  entry.count++;
  rateLimits.set(sessionId, entry);

  // Clean up old entries
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
