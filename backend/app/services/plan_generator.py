"""
Plan generation service using Claude tool_use.
Contains the exact schema and prompts from the original JS implementation.
"""

# Tool definition for structured plan output - EXACT PORT FROM JS
GENERATE_PLAN_TOOL = {
    "name": "generate_annual_plan",
    "description": "Generate a complete 52-week periodized training plan for an athlete or squad. Call this tool with the full plan data.",
    "input_schema": {
        "type": "object",
        "required": ["athlete", "season", "eventGroup", "periodization", "seasonStart", "competitions", "weeks"],
        "properties": {
            "athlete": {
                "type": "string",
                "description": "Name of athlete or squad"
            },
            "season": {
                "type": "string",
                "description": "Season year range, e.g., '2025/2026'"
            },
            "eventGroup": {
                "type": "string",
                "description": "Event category: sprints, long-sprints, middle-distance, endurance, hurdles, jumps, throws, multi-events"
            },
            "periodization": {
                "type": "string",
                "enum": ["bi-phase", "single-peak"],
                "description": "Periodization approach"
            },
            "trainingLevel": {
                "type": "string",
                "enum": ["beginner", "amateur", "elite"],
                "description": "Training level of the athlete"
            },
            "seasonStart": {
                "type": "string",
                "description": "ISO date of week 1 Monday (typically late August/early September)"
            },
            "competitions": {
                "type": "array",
                "description": "List of target competitions",
                "items": {
                    "type": "object",
                    "required": ["name", "date", "weekNum", "importance"],
                    "properties": {
                        "name": {"type": "string", "description": "Competition name"},
                        "date": {"type": "string", "description": "ISO date of competition"},
                        "weekNum": {"type": "integer", "minimum": 1, "maximum": 52, "description": "Week number (1-52)"},
                        "importance": {"type": "integer", "enum": [1, 2, 3], "description": "1=major, 2=moderate, 3=minor"}
                    }
                }
            },
            "weeks": {
                "type": "array",
                "description": "All 52 weeks of the training plan",
                "minItems": 52,
                "maxItems": 52,
                "items": {
                    "type": "object",
                    "required": ["weekNum", "startDate", "month", "phase", "phaseType", "load"],
                    "properties": {
                        "weekNum": {"type": "integer", "minimum": 1, "maximum": 52},
                        "startDate": {"type": "string", "description": "ISO date (Monday of that week)"},
                        "month": {"type": "string", "description": "Display month, e.g., 'Sep 25'"},
                        "phase": {"type": "string", "description": "Training phase name"},
                        "phaseType": {
                            "type": "string",
                            "enum": ["general-prep", "special-prep", "competition", "taper"],
                            "description": "Phase category for visualization"
                        },
                        "block": {"type": "string", "description": "Training block name"},
                        "load": {"type": "integer", "minimum": 0, "maximum": 4, "description": "Training load 0-4"},
                        "competitions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Competition names this week"
                        },
                        "competitionImportance": {
                            "type": ["integer", "null"],
                            "description": "Importance of competition this week (1-3) or null"
                        },
                        "technical": {"type": "string", "description": "Technical focus for the week"},
                        "physical": {"type": "string", "description": "Physical development focus"}
                    }
                }
            }
        }
    }
}

# System prompt for plan generation - EXACT PORT FROM JS
GENERATION_SYSTEM_PROMPT = """You are an expert athletics coach generating a 52-week periodized annual training plan.

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

CRITICAL REQUIREMENTS:
1. You MUST generate EXACTLY 52 weeks - no more, no less
2. The weeks array MUST contain all 52 weeks from week 1 to week 52
3. Do NOT stop early or abbreviate - every single week must be included
4. Call the generate_annual_plan tool with the COMPLETE 52-week plan

Do not output JSON directly - use the tool."""


def build_context_message(form_data: dict, messages: list[dict] | None = None) -> str:
    """
    Build context message from form data and conversation history.
    """
    periodization_text = (
        "Bi-phase (indoor + outdoor peaks)"
        if form_data.get("periodization") == "bi-phase"
        else "Single-peak"
    )

    age_groups = form_data.get("ageGroups") or ["Senior"]
    age_groups_text = ", ".join(age_groups) if isinstance(age_groups, list) else age_groups

    training_level = form_data.get("trainingLevel", "amateur")
    training_level_text = {
        "beginner": "Beginner (new to structured training)",
        "amateur": "Amateur (club level)",
        "elite": "Elite (national/international level)"
    }.get(training_level, "Amateur")

    context = f"""Generate a 52-week annual training plan with the following details:

**Athlete/Squad:** {form_data.get('athleteName', 'Unknown')}
**Event Group:** {form_data.get('eventGroup', 'Unknown')}
**Age Group(s):** {age_groups_text}
**Training Level:** {training_level_text}
**Country:** {form_data.get('country', 'Not specified')}
**Season:** {form_data.get('season', 'Unknown')}
**Periodization:** {periodization_text}
**Target Competitions:** {form_data.get('targetCompetitions') or 'Not specified'}
"""

    # Add relevant conversation context if any
    if messages:
        context += "\n## Conversation Context\n"
        for msg in messages:
            role = "User" if msg.get("role") == "user" else "Coach"
            context += f"{role}: {msg.get('content', '')}\n\n"

    context += "\nNow generate the complete 52-week plan using the generate_annual_plan tool."

    return context
