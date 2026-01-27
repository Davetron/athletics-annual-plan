/**
 * System prompt for Claude chat - CONCISE competition confirmation
 */

export const SYSTEM_PROMPT = `You are a concise athletics coach assistant. Your ONLY job is to present a competition list for confirmation.

## RULES
- Be BRIEF - no lengthy explanations
- Do NOT ask about events, level, or country - this info is already provided
- Present competitions as a simple list with dates and priority
- After presenting, ask user to confirm or adjust, then click "Generate Plan"

## PRIORITY LEVELS
- **A-Priority:** National Championships, major international events (1-2 per season)
- **B-Priority:** Regional championships, key tune-ups (3-5 per season)
- **C-Priority:** League meets, openers, training races (as needed)

## RESPONSE FORMAT
Keep it short:

"Based on your selections, here are the key competitions for [season]:

**A-Priority (Peak):**
• [Event] - [Month]

**B-Priority (Important):**
• [Event] - [Month]

**C-Priority (Development):**
• [Event] - [Month]

Adjust if needed, then click **Generate Plan** when ready."

If user asks questions, answer briefly then redirect to confirming the list.`;

/**
 * Create initial message with all form context
 */
export function createInitialContext(formData) {
  const ageGroups = formData.ageGroups || ['Senior'];
  const ageGroupText = ageGroups.join(', ');

  const trainingLevelText = {
    'beginner': 'Beginner (new to structured training)',
    'amateur': 'Amateur (club level)',
    'elite': 'Elite (national/international level)'
  }[formData.trainingLevel] || 'Amateur';

  const compLevels = formData.compLevels || [];
  const compScopeText = compLevels.length > 0
    ? compLevels.map(l => {
        if (l === 'national') return 'National Championships';
        if (l === 'european') return 'European Championships';
        if (l === 'world') return 'World Championships';
        if (l === 'leagues') return 'League/Graded Meets';
        return l;
      }).join(', ')
    : 'National only';

  return `Create a competition list for:

**Athlete/Squad:** ${formData.athleteName}
**Event Group:** ${formData.eventGroup}
**Age Group(s):** ${ageGroupText}
**Training Level:** ${trainingLevelText}
**Country:** ${formData.country}
**Season:** ${formData.season}
**Periodization:** ${formData.periodization === 'bi-phase' ? 'Bi-phase (indoor + outdoor)' : 'Single-peak'}
**Competition Scope:** ${compScopeText}
${formData.targetCompetitions ? `**Notes:** ${formData.targetCompetitions}` : ''}

Present the relevant competitions for this athlete to confirm.`;
}

// Unused but kept for compatibility
export function createPlanContext(plan) {
  return '';
}

export const PLAN_DISCUSSION_PROMPT = SYSTEM_PROMPT;
