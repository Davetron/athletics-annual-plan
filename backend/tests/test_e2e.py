"""
End-to-end tests for the Athletics Annual Plan API.

These tests use REAL Claude API calls to verify the complete flow:
1. Validate invite code -> get session ID
2. Chat with Claude
3. Generate plan
4. Download Excel
5. Search competitions

Set CLAUDE_API_KEY environment variable to run these tests.
Tests requiring the API will be skipped if the key is not available.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.database import engine, Base, async_session, InviteCode
from app.config import get_settings


# Check if API key is available
HAS_API_KEY = bool(os.environ.get("CLAUDE_API_KEY") or get_settings().claude_api_key)
requires_api = pytest.mark.skipif(not HAS_API_KEY, reason="CLAUDE_API_KEY not set")


@pytest.fixture(scope="function")
async def setup_db():
    """Create fresh database for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed test invite code
    async with async_session() as session:
        test_code = InviteCode(code="TESTCODE", max_uses=100, active=True)
        limited_code = InviteCode(code="LIMITED", max_uses=2, used_count=2, active=True)
        inactive_code = InviteCode(code="INACTIVE", max_uses=100, active=False)
        session.add_all([test_code, limited_code, inactive_code])
        await session.commit()

    yield

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(setup_db):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# =============================================================================
# Auth Tests (no API key required)
# =============================================================================

@pytest.mark.asyncio
async def test_validate_code_success(client):
    """Test successful invite code validation."""
    response = await client.post(
        "/api/validate-code",
        json={"code": "TESTCODE"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["session_id"] is not None
    assert len(data["session_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_validate_code_invalid(client):
    """Test invalid invite code rejection."""
    response = await client.post(
        "/api/validate-code",
        json={"code": "INVALID"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["error"] == "Invalid invite code"


@pytest.mark.asyncio
async def test_validate_code_case_insensitive(client):
    """Test that invite codes are case-insensitive."""
    response = await client.post(
        "/api/validate-code",
        json={"code": "testcode"}  # lowercase
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True


@pytest.mark.asyncio
async def test_validate_code_inactive(client):
    """Test that inactive codes are rejected."""
    response = await client.post(
        "/api/validate-code",
        json={"code": "INACTIVE"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "deactivated" in data["error"]


@pytest.mark.asyncio
async def test_validate_code_usage_limit(client):
    """Test that codes at usage limit are rejected."""
    response = await client.post(
        "/api/validate-code",
        json={"code": "LIMITED"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert "usage limit" in data["error"]


@pytest.mark.asyncio
async def test_validate_code_increments_usage(client):
    """Test that validating a code increments its usage count."""
    # First use
    response1 = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    assert response1.json()["valid"] is True
    remaining1 = response1.json()["remaining_uses"]

    # Second use
    response2 = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    assert response2.json()["valid"] is True
    remaining2 = response2.json()["remaining_uses"]

    # Check remaining uses decreased
    assert remaining2 == remaining1 - 1


# =============================================================================
# Session Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_chat_requires_session_id(client):
    """Test that chat endpoint requires X-Session-ID header."""
    response = await client.post(
        "/api/chat",
        json={
            "system": "You are a helpful assistant.",
            "messages": [{"role": "user", "content": "Hello"}]
        }
    )

    assert response.status_code == 401
    assert "Session ID required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_generate_plan_requires_session_id(client):
    """Test that generate-plan endpoint requires X-Session-ID header."""
    response = await client.post(
        "/api/generate-plan",
        json={
            "formData": {
                "athleteName": "Test Athlete",
                "eventGroup": "sprints",
                "season": "2025/2026",
                "periodization": "bi-phase",
                "ageGroups": ["Senior"],
                "trainingLevel": "amateur",
                "country": "Ireland",
                "compLevels": ["National"],
                "targetCompetitions": "National Championships"
            }
        }
    )

    assert response.status_code == 401


# =============================================================================
# URL Fetch Tests (no API key required)
# =============================================================================

@pytest.mark.asyncio
async def test_fetch_url_invalid(client):
    """Test fetch-url rejects invalid URLs."""
    response = await client.post(
        "/api/fetch-url",
        json={"url": "not-a-valid-url"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Invalid URL" in data["error"]


@pytest.mark.asyncio
async def test_fetch_url_invalid_protocol(client):
    """Test fetch-url rejects non-HTTP protocols."""
    response = await client.post(
        "/api/fetch-url",
        json={"url": "ftp://example.com/file"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False


# =============================================================================
# Excel Download Tests (no API key required)
# =============================================================================

def create_mock_plan(athlete="Test Athlete", season="2025/2026"):
    """Create a valid 52-week plan for testing."""
    weeks = []
    for i in range(52):
        week_num = i + 1
        # Determine phase based on week number (bi-phase periodization)
        if week_num <= 3:
            phase, phase_type = "Transition", "taper"
        elif week_num <= 14:
            phase, phase_type = "General Prep I", "general-prep"
        elif week_num <= 18:
            phase, phase_type = "Special Prep I", "special-prep"
        elif week_num <= 27:
            phase, phase_type = "Competition I", "competition"
        elif week_num <= 28:
            phase, phase_type = "Transition", "taper"
        elif week_num <= 33:
            phase, phase_type = "General Prep II", "general-prep"
        elif week_num <= 37:
            phase, phase_type = "Special Prep II", "special-prep"
        elif week_num <= 45:
            phase, phase_type = "Competition II", "competition"
        else:
            phase, phase_type = "End of Season", "taper"

        weeks.append({
            "weekNum": week_num,
            "startDate": f"2025-{((i // 4) % 12) + 1:02d}-{(i % 4) * 7 + 1:02d}",
            "month": ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"][(i // 4) % 12] + " 25",
            "phase": phase,
            "phaseType": phase_type,
            "block": f"Block {(i // 8) + 1}",
            "load": 2 if phase_type == "taper" else 3,
            "competitions": [],
            "competitionImportance": None,
            "technical": "Event-specific drills",
            "physical": "Base building" if "Prep" in phase else "Maintenance"
        })

    return {
        "athlete": athlete,
        "season": season,
        "eventGroup": "sprints",
        "periodization": "bi-phase",
        "seasonStart": "2025-08-25",
        "competitions": [],
        "weeks": weeks
    }


@pytest.mark.asyncio
async def test_download_excel_basic(client):
    """Test basic Excel file generation."""
    plan = create_mock_plan()

    response = await client.post(
        "/api/download-excel",
        json={"plan": plan}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in response.headers.get("content-disposition", "")

    # Verify it's a valid Excel file (starts with PK for zip format)
    content = response.content
    assert content[:2] == b"PK"
    assert len(content) > 1000  # Should be a reasonable size


@pytest.mark.asyncio
async def test_download_excel_with_competitions(client):
    """Test Excel generation with competition data."""
    plan = create_mock_plan()

    # Add a competition in week 20
    plan["weeks"][19]["competitions"] = ["National Indoor Championships"]
    plan["weeks"][19]["competitionImportance"] = 1

    # Add another in week 42
    plan["weeks"][41]["competitions"] = ["National Outdoor Championships"]
    plan["weeks"][41]["competitionImportance"] = 1

    plan["competitions"] = [
        {"name": "National Indoor Championships", "date": "2026-02-15", "weekNum": 20, "importance": 1},
        {"name": "National Outdoor Championships", "date": "2026-07-20", "weekNum": 42, "importance": 1}
    ]

    response = await client.post(
        "/api/download-excel",
        json={"plan": plan}
    )

    assert response.status_code == 200
    assert len(response.content) > 1000


@pytest.mark.asyncio
async def test_download_excel_filename(client):
    """Test that Excel filename is properly formatted."""
    plan = create_mock_plan(athlete="Sprint Squad", season="2025/2026")

    response = await client.post(
        "/api/download-excel",
        json={"plan": plan}
    )

    assert response.status_code == 200
    content_disposition = response.headers.get("content-disposition", "")
    assert "Sprint" in content_disposition or "sprint" in content_disposition.lower()
    assert "2025" in content_disposition


# =============================================================================
# Chat Tests (requires API key)
# =============================================================================

@requires_api
@pytest.mark.asyncio
async def test_chat_real_api(client):
    """Test chat endpoint with real Claude API."""
    # First get a session ID
    auth_response = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    session_id = auth_response.json()["session_id"]

    response = await client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={
            "system": "You are a track and field coach. Respond briefly.",
            "messages": [{"role": "user", "content": "What's the most important phase in a sprinter's annual plan?"}]
        },
        timeout=60.0
    )

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert len(data["content"]) > 0

    # Check that we got a text response
    text_content = next((block for block in data["content"] if block.get("type") == "text"), None)
    assert text_content is not None
    assert len(text_content.get("text", "")) > 10


# =============================================================================
# Plan Generation Tests (requires API key)
# =============================================================================

@requires_api
@pytest.mark.asyncio
async def test_generate_plan_real_api(client):
    """Test plan generation with real Claude API."""
    # Get a session ID
    auth_response = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    session_id = auth_response.json()["session_id"]

    response = await client.post(
        "/api/generate-plan",
        headers={"X-Session-ID": session_id},
        json={
            "formData": {
                "athleteName": "Test Sprinter",
                "eventGroup": "sprints",
                "season": "2025/2026",
                "periodization": "bi-phase",
                "ageGroups": ["Senior"],
                "trainingLevel": "amateur",
                "country": "Ireland",
                "compLevels": ["National", "European"],
                "targetCompetitions": "National Indoor Championships in February, National Outdoor Championships in July"
            }
        },
        timeout=120.0  # Plan generation can take a while
    )

    assert response.status_code == 200
    data = response.json()
    if not data["success"]:
        print(f"Plan generation failed: {data.get('error')}")
    assert data["success"] is True, f"Plan generation failed: {data.get('error')}"
    assert data["plan"] is not None

    plan = data["plan"]

    # Validate plan structure
    assert plan["athlete"] == "Test Sprinter"
    assert plan["season"] == "2025/2026"
    assert plan["eventGroup"] == "sprints"
    assert plan["periodization"] == "bi-phase"
    assert len(plan["weeks"]) == 52

    # Validate week structure
    for i, week in enumerate(plan["weeks"]):
        assert week["weekNum"] == i + 1
        assert "startDate" in week
        assert "month" in week
        assert "phase" in week
        assert week["phaseType"] in ["general-prep", "special-prep", "competition", "taper"]
        assert 0 <= week["load"] <= 4


@requires_api
@pytest.mark.asyncio
async def test_generate_plan_single_peak(client):
    """Test plan generation with single-peak periodization."""
    auth_response = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    session_id = auth_response.json()["session_id"]

    response = await client.post(
        "/api/generate-plan",
        headers={"X-Session-ID": session_id},
        json={
            "formData": {
                "athleteName": "Marathon Runner",
                "eventGroup": "endurance",
                "season": "2025/2026",
                "periodization": "single-peak",
                "ageGroups": ["Senior"],
                "trainingLevel": "elite",
                "country": "United Kingdom",
                "compLevels": ["National", "World"],
                "targetCompetitions": "City Marathon in April"
            }
        },
        timeout=120.0
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"]["periodization"] == "single-peak"
    assert len(data["plan"]["weeks"]) == 52


# =============================================================================
# Competition Search Tests (requires API key)
# =============================================================================

@requires_api
@pytest.mark.asyncio
async def test_search_competitions_real_api(client):
    """Test competition search with real Claude API + web search."""
    response = await client.post(
        "/api/search-competitions",
        json={
            "country": "Ireland",
            "athlete_type": "Senior",
            "season_year": "2025/2026",
            "include_european": True,
            "include_world": False
        },
        timeout=120.0  # Web search can take a while
    )

    assert response.status_code == 200
    data = response.json()
    if not data["success"]:
        print(f"Search competitions failed: {data.get('error')}")
    assert data["success"] is True, f"Search failed: {data.get('error')}"

    # Should find some competitions (may vary based on search results)
    if data["competitions"]:
        comp = data["competitions"][0]
        assert "name" in comp
        assert "date" in comp
        assert "importance" in comp


# =============================================================================
# Full End-to-End Flow Tests (requires API key)
# =============================================================================

@requires_api
@pytest.mark.asyncio
async def test_full_flow_with_real_api(client):
    """
    Test the complete user flow with real Claude API calls:
    1. Login with invite code
    2. Generate a training plan
    3. Download as Excel
    """
    # Step 1: Validate invite code
    auth_response = await client.post(
        "/api/validate-code",
        json={"code": "TESTCODE"}
    )
    assert auth_response.status_code == 200
    session_id = auth_response.json()["session_id"]
    assert session_id is not None

    # Step 2: Generate plan with Claude
    plan_response = await client.post(
        "/api/generate-plan",
        headers={"X-Session-ID": session_id},
        json={
            "formData": {
                "athleteName": "E2E Test Athlete",
                "eventGroup": "hurdles",
                "season": "2025/2026",
                "periodization": "bi-phase",
                "ageGroups": ["Senior", "U23"],
                "trainingLevel": "amateur",
                "country": "Ireland",
                "compLevels": ["National"],
                "targetCompetitions": "National Championships"
            }
        },
        timeout=120.0
    )

    assert plan_response.status_code == 200
    plan_data = plan_response.json()
    assert plan_data["success"] is True

    plan = plan_data["plan"]
    assert len(plan["weeks"]) == 52

    # Step 3: Download Excel
    excel_response = await client.post(
        "/api/download-excel",
        json={"plan": plan}
    )

    assert excel_response.status_code == 200
    assert excel_response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Verify Excel content
    content = excel_response.content
    assert len(content) > 1000
    assert content[:2] == b"PK"  # ZIP signature


@requires_api
@pytest.mark.asyncio
async def test_generate_plan_masters_athlete(client):
    """Test plan generation for Masters athletes with multiple age groups."""
    auth_response = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    session_id = auth_response.json()["session_id"]

    response = await client.post(
        "/api/generate-plan",
        headers={"X-Session-ID": session_id},
        json={
            "formData": {
                "athleteName": "Masters Throws Group",
                "eventGroup": "throws",
                "season": "2025/2026",
                "periodization": "single-peak",
                "ageGroups": ["Masters"],
                "trainingLevel": "beginner",
                "country": "United States",
                "compLevels": ["National", "World"],
                "targetCompetitions": "World Masters Athletics Championships"
            }
        },
        timeout=120.0
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["plan"]["periodization"] == "single-peak"
    assert len(data["plan"]["weeks"]) == 52


@requires_api
@pytest.mark.asyncio
async def test_chat_then_generate_flow(client):
    """
    Test the flow where user chats first, then generates a plan.
    The chat context should influence the generated plan.
    """
    # Login
    auth_response = await client.post("/api/validate-code", json={"code": "TESTCODE"})
    session_id = auth_response.json()["session_id"]

    # Chat with the coach
    chat_response = await client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={
            "system": "You are a track and field coach helping plan a training season.",
            "messages": [
                {"role": "user", "content": "I'm a 400m runner preparing for the European Championships in August."}
            ]
        },
        timeout=60.0
    )
    assert chat_response.status_code == 200

    # Get the assistant's response
    chat_data = chat_response.json()
    assistant_msg = next(
        (block["text"] for block in chat_data.get("content", []) if block.get("type") == "text"),
        ""
    )

    # Generate plan with chat context
    plan_response = await client.post(
        "/api/generate-plan",
        headers={"X-Session-ID": session_id},
        json={
            "formData": {
                "athleteName": "400m Specialist",
                "eventGroup": "long-sprints",
                "season": "2025/2026",
                "periodization": "bi-phase",
                "ageGroups": ["Senior"],
                "trainingLevel": "elite",
                "country": "Germany",
                "compLevels": ["National", "European"],
                "targetCompetitions": "European Championships in August"
            },
            "messages": [
                {"role": "user", "content": "I'm a 400m runner preparing for the European Championships in August."},
                {"role": "assistant", "content": assistant_msg}
            ]
        },
        timeout=120.0
    )

    assert plan_response.status_code == 200
    plan_data = plan_response.json()
    assert plan_data["success"] is True
    assert len(plan_data["plan"]["weeks"]) == 52
