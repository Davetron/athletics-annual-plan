"""
Competition-related routes - URL fetching and competition search.
"""

import json
import re
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
import httpx

from app.config import get_settings
from app.models.schemas import (
    FetchUrlRequest,
    FetchUrlResponse,
    SearchCompetitionsRequest,
    SearchCompetitionsResponse,
    CompetitionResult,
)

router = APIRouter()
settings = get_settings()


def html_to_text(html: str) -> str:
    """
    Convert HTML to readable text.
    Strips tags but preserves some structure.
    """
    # Remove script and style elements
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<head[^>]*>[\s\S]*?</head>", "", text, flags=re.IGNORECASE)

    # Convert common elements to text equivalents
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<td[^>]*>", "\t", text, flags=re.IGNORECASE)
    text = re.sub(r"<th[^>]*>", "\t", text, flags=re.IGNORECASE)

    # Remove remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode HTML entities
    entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&rsquo;": "'",
        "&lsquo;": "'",
        "&rdquo;": '"',
        "&ldquo;": '"',
        "&ndash;": "–",
        "&mdash;": "—",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)

    # Clean up whitespace
    text = re.sub(r"\t+", "\t", text)
    text = re.sub(r"[ ]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


@router.post("/fetch-url", response_model=FetchUrlResponse)
async def fetch_url(request: FetchUrlRequest):
    """
    Fetch a URL and return the text content for Claude to parse.
    Used for fetching federation competition calendars.
    """
    url = request.url

    # Validate URL
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Invalid protocol")
    except Exception:
        return FetchUrlResponse(success=False, error="Invalid URL")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AthleticsAnnualPlan/1.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                follow_redirects=True,
                timeout=30.0,
            )

            if response.status_code != 200:
                return FetchUrlResponse(
                    success=False,
                    error=f"Failed to fetch URL: {response.status_code} {response.reason_phrase}",
                )

            html = response.text
            text = html_to_text(html)

            # Limit response size to avoid overwhelming Claude
            max_length = 15000
            truncated = len(text) > max_length
            content = (
                text[:max_length] + "\n\n[Content truncated...]"
                if truncated
                else text
            )

            return FetchUrlResponse(
                success=True,
                url=url,
                content=content,
                truncated=truncated,
                original_length=len(text),
            )

    except httpx.TimeoutException:
        return FetchUrlResponse(success=False, error="Request timed out")
    except httpx.RequestError as e:
        return FetchUrlResponse(success=False, error=f"Failed to fetch URL: {str(e)}")


@router.post("/search-competitions", response_model=SearchCompetitionsResponse)
async def search_competitions(request: SearchCompetitionsRequest):
    """
    Search for athletics competitions using Claude API with web search.

    Uses Claude's web_search tool to find real competition dates.
    """
    if not settings.claude_api_key:
        raise HTTPException(status_code=500, detail="Claude API key not configured")

    start_year = int(request.season_year.split("/")[0])
    end_year = int(request.season_year.split("/")[1])

    # Build age groups text
    age_groups_text = ", ".join(request.age_groups)
    is_masters = "Masters" in request.age_groups

    # Build competition levels requirements
    comp_requirements = []
    if "National" in request.comp_levels:
        comp_requirements.append(f"- National Indoor Championships (typically Jan-Mar {end_year})")
        comp_requirements.append(f"- National Outdoor Championships (typically Jun-Aug {end_year})")
        comp_requirements.append("- Regional/Provincial Championships")
    if "European" in request.comp_levels:
        if is_masters:
            comp_requirements.append("- European Masters Indoor Championships")
            comp_requirements.append("- European Masters Outdoor Championships")
        else:
            comp_requirements.append("- European Indoor Championships (if applicable)")
            comp_requirements.append("- European Outdoor Championships (if applicable)")
    if "World" in request.comp_levels:
        if is_masters:
            comp_requirements.append("- World Masters Athletics Championships")
        else:
            comp_requirements.append("- World Indoor Championships (if applicable)")
            comp_requirements.append("- World Outdoor Championships (if applicable)")
    if "Leagues" in request.comp_levels:
        comp_requirements.append("- National League events")
        comp_requirements.append("- Graded meets or open competitions")

    comp_list = "\n".join(comp_requirements) if comp_requirements else "- National Championships"

    # Federation URL hint
    federation_hint = ""
    if request.federation_url:
        federation_hint = f"\n\nStart by checking the official fixtures at: {request.federation_url}"

    prompt = f"""Search for track and field athletics competitions for the {request.season_year} season in {request.country}.

I need competitions suitable for {age_groups_text} athletes in {request.event_group} events.

Competitions to find:
{comp_list}{federation_hint}

Return the competitions as a JSON array sorted by date, with this format:
```json
[
  {{
    "name": "Competition Name",
    "date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "location": "City, Country",
    "importance": 1,
    "type": "indoor"
  }}
]
```

Importance levels:
- 1 = Major championship (Nationals, Europeans, Worlds)
- 2 = Significant (Regional championships, major leagues)
- 3 = Development (Graded meets, open competitions)

Type should be "indoor" or "outdoor".

Only return the JSON array, no other text."""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": settings.claude_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 4096,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120.0,
            )

            if response.status_code != 200:
                error_detail = response.text[:500] if response.text else "No details"
                print(f"[DEBUG] Search competitions API error: {response.status_code} - {error_detail}")
                return SearchCompetitionsResponse(
                    success=False,
                    error=f"Failed to search for competitions (status {response.status_code})",
                )

            data = response.json()

            # Extract text from response (handles multiple content blocks)
            response_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    response_text += block.get("text", "")

            # Parse JSON from response
            competitions = []
            try:
                start_idx = response_text.find("[")
                end_idx = response_text.rfind("]") + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    raw_competitions = json.loads(json_str)

                    for comp in raw_competitions:
                        competitions.append(
                            CompetitionResult(
                                name=comp.get("name", "Unknown"),
                                date=comp.get("date", ""),
                                end_date=comp.get("end_date"),
                                location=comp.get("location"),
                                importance=comp.get("importance", 3),
                                type=comp.get("type"),
                            )
                        )
            except json.JSONDecodeError:
                pass

            return SearchCompetitionsResponse(
                success=True,
                competitions=competitions,
            )

    except httpx.TimeoutException:
        return SearchCompetitionsResponse(
            success=False,
            error="Search request timed out",
        )
    except httpx.RequestError as e:
        return SearchCompetitionsResponse(
            success=False,
            error=f"Failed to search: {str(e)}",
        )
