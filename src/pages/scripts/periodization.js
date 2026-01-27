/**
 * Periodization Rules Engine
 * Handles instant rules-based adjustments when competitions/phases change
 * For major changes (A-priority add/remove), signals need for AI regeneration
 */

/**
 * Apply taper rules around a competition
 * Called when a competition is added or moved
 *
 * @param {Object} plan - The full plan object
 * @param {number} weekIndex - 0-based index of the competition week
 * @param {number} importance - 1 (A), 2 (B), or 3 (C) priority
 * @returns {Object} - Modified plan
 */
export function applyTaperRules(plan, weekIndex, importance) {
  const weeks = plan.weeks;

  // Rule 1: Competition week load = 1 (low)
  if (weekIndex >= 0 && weekIndex < weeks.length) {
    weeks[weekIndex].load = 1;
  }

  // Rule 2: Week before (taper) load = 1
  if (weekIndex - 1 >= 0) {
    weeks[weekIndex - 1].load = 1;
  }

  // Rule 3: Two weeks before load = 2 (reduced)
  if (weekIndex - 2 >= 0) {
    weeks[weekIndex - 2].load = 2;
  }

  // Rule 4: Set phase based on priority
  if (importance === 1) {
    // A-priority: set competition phase for weeks N-2 to N
    for (let i = Math.max(0, weekIndex - 2); i <= weekIndex && i < weeks.length; i++) {
      weeks[i].phaseType = 'competition';
      weeks[i].phase = 'Competition';
    }
  } else if (importance === 2) {
    // B-priority: set competition phase for week N only
    if (weekIndex >= 0 && weekIndex < weeks.length) {
      weeks[weekIndex].phaseType = 'competition';
      weeks[weekIndex].phase = 'Competition';
    }
  }
  // C-priority: no phase change

  return plan;
}

/**
 * Remove competition effects from a week
 * Resets load and phase to reasonable defaults
 *
 * @param {Object} plan - The full plan object
 * @param {number} weekIndex - 0-based index of the week
 * @param {number} oldImportance - Previous importance level
 * @returns {Object} - Modified plan
 */
export function removeCompetitionEffects(plan, weekIndex, oldImportance) {
  const weeks = plan.weeks;

  // Reset load to medium (2) for affected weeks
  if (weekIndex >= 0 && weekIndex < weeks.length) {
    weeks[weekIndex].load = 2;
  }
  if (weekIndex - 1 >= 0) {
    weeks[weekIndex - 1].load = 2;
  }
  if (weekIndex - 2 >= 0) {
    weeks[weekIndex - 2].load = 2;
  }

  // Reset phase if this was A/B priority
  if (oldImportance <= 2) {
    // Try to restore to surrounding phase context
    const surroundingPhase = getSurroundingPhase(weeks, weekIndex);

    if (oldImportance === 1) {
      // A-priority affected weeks N-2 to N
      for (let i = Math.max(0, weekIndex - 2); i <= weekIndex && i < weeks.length; i++) {
        weeks[i].phaseType = surroundingPhase.type;
        weeks[i].phase = surroundingPhase.name;
      }
    } else {
      // B-priority only affected week N
      weeks[weekIndex].phaseType = surroundingPhase.type;
      weeks[weekIndex].phase = surroundingPhase.name;
    }
  }

  return plan;
}

/**
 * Get the phase from surrounding weeks (for restoration)
 */
function getSurroundingPhase(weeks, weekIndex) {
  // Look at weeks before and after the affected range
  const checkBefore = weekIndex - 3;
  const checkAfter = weekIndex + 1;

  if (checkBefore >= 0 && weeks[checkBefore].phaseType !== 'competition') {
    return { type: weeks[checkBefore].phaseType, name: weeks[checkBefore].phase };
  }
  if (checkAfter < weeks.length && weeks[checkAfter].phaseType !== 'competition') {
    return { type: weeks[checkAfter].phaseType, name: weeks[checkAfter].phase };
  }

  // Default to general-prep if can't determine
  return { type: 'general-prep', name: 'General Prep' };
}

/**
 * Check if a change requires AI regeneration
 *
 * @param {string} changeType - Type of change
 * @param {Object} details - Change details
 * @returns {boolean} - True if AI should regenerate
 */
export function needsAIRegeneration(changeType, details = {}) {
  switch (changeType) {
    case 'competition-add':
      // Adding A-priority requires full regen
      return details.importance === 1;

    case 'competition-remove':
      // Removing A-priority requires full regen
      return details.oldImportance === 1;

    case 'competition-change':
      // Changing to/from A-priority requires full regen
      return details.newImportance === 1 || details.oldImportance === 1;

    case 'competition-move':
      // Moving A-priority requires full regen
      return details.importance === 1;

    case 'phase-change':
      // Manual phase changes don't need AI (user is overriding)
      return false;

    case 'load-change':
      // Manual load changes don't need AI
      return false;

    default:
      return false;
  }
}

/**
 * Apply rules-based adjustments to plan
 * This is the main entry point for instant updates
 *
 * @param {Object} plan - The full plan object
 * @param {string} changeType - Type of change
 * @param {Object} details - Change details (weekIndex, importance, etc.)
 * @returns {Object} - { plan, needsRegeneration }
 */
export function applyRulesBasedUpdate(plan, changeType, details) {
  let needsRegen = false;

  switch (changeType) {
    case 'competition-add':
      plan = applyTaperRules(plan, details.weekIndex, details.importance);
      needsRegen = needsAIRegeneration(changeType, details);
      break;

    case 'competition-remove':
      plan = removeCompetitionEffects(plan, details.weekIndex, details.oldImportance);
      needsRegen = needsAIRegeneration(changeType, details);
      break;

    case 'competition-move':
      // Remove from old position, add to new
      plan = removeCompetitionEffects(plan, details.oldWeekIndex, details.importance);
      plan = applyTaperRules(plan, details.newWeekIndex, details.importance);
      needsRegen = needsAIRegeneration(changeType, details);
      break;

    case 'phase-change':
    case 'load-change':
      // These are already handled by spreadsheet.js directly
      // No additional processing needed
      break;
  }

  return {
    plan,
    needsRegeneration: needsRegen
  };
}

/**
 * Validate plan structure
 * Ensures all required fields exist and values are in range
 *
 * @param {Object} plan - Plan to validate
 * @returns {Object} - { valid, errors }
 */
export function validatePlan(plan) {
  const errors = [];

  if (!plan) {
    return { valid: false, errors: ['Plan is null or undefined'] };
  }

  if (!plan.weeks || !Array.isArray(plan.weeks)) {
    return { valid: false, errors: ['Plan missing weeks array'] };
  }

  if (plan.weeks.length !== 52) {
    errors.push(`Plan has ${plan.weeks.length} weeks, expected 52`);
  }

  plan.weeks.forEach((week, i) => {
    if (typeof week.load !== 'number' || week.load < 0 || week.load > 4) {
      errors.push(`Week ${i + 1}: invalid load value ${week.load}`);
    }
    if (!week.phaseType) {
      errors.push(`Week ${i + 1}: missing phaseType`);
    }
  });

  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Calculate season statistics
 *
 * @param {Object} plan - The plan object
 * @returns {Object} - Statistics about the plan
 */
export function calculatePlanStats(plan) {
  const weeks = plan.weeks || [];

  const stats = {
    totalWeeks: weeks.length,
    competitions: {
      total: 0,
      aPriority: 0,
      bPriority: 0,
      cPriority: 0,
    },
    phases: {
      'general-prep': 0,
      'special-prep': 0,
      'competition': 0,
      'taper': 0,
    },
    averageLoad: 0,
  };

  let totalLoad = 0;

  weeks.forEach(week => {
    // Count competitions
    if (week.competitions && week.competitions.length > 0) {
      stats.competitions.total++;
      if (week.competitionImportance === 1) stats.competitions.aPriority++;
      else if (week.competitionImportance === 2) stats.competitions.bPriority++;
      else stats.competitions.cPriority++;
    }

    // Count phases
    if (week.phaseType && stats.phases.hasOwnProperty(week.phaseType)) {
      stats.phases[week.phaseType]++;
    }

    // Sum load
    totalLoad += week.load || 0;
  });

  stats.averageLoad = weeks.length > 0 ? (totalLoad / weeks.length).toFixed(1) : 0;

  return stats;
}
