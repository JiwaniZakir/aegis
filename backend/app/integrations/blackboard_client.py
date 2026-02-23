"""Blackboard Learn integration — courses, assignments, grades via REST API."""

from __future__ import annotations

import uuid
from datetime import datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.assignment import Assignment

logger = structlog.get_logger()


class BlackboardAuthError(Exception):
    """Raised when Blackboard authentication fails."""


class BlackboardClient(BaseIntegration):
    """Integration client for Blackboard Learn REST API.

    Falls back to stored credentials for authentication.
    Same interface as CanvasClient for consistent aggregation.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._base_url = settings.blackboard_url.rstrip("/") if settings.blackboard_url else ""
        self._access_token: str | None = None

    async def _authenticate(self) -> str:
        """Authenticate with Blackboard and get an access token."""
        if self._access_token:
            return self._access_token

        try:
            self._access_token = await self.get_credential("blackboard_access_token")
            return self._access_token
        except KeyError:
            pass

        # Try OAuth client credentials flow
        try:
            client_id = await self.get_credential("blackboard_client_id")
            client_secret = await self.get_credential("blackboard_client_secret")
        except KeyError as exc:
            msg = "No Blackboard credentials configured"
            raise BlackboardAuthError(msg) from exc

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/learn/api/public/v1/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()

        self._access_token = data["access_token"]
        await self.store_credential("blackboard_access_token", self._access_token)
        self._log.info("blackboard_authenticated")
        return self._access_token

    async def _api_request(self, path: str, *, params: dict | None = None) -> dict | list:
        """Make an authenticated GET request to the Blackboard API."""
        token = await self._authenticate()
        url = f"{self._base_url}/learn/api/public/v3{path}"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                self._access_token = None
                token = await self._authenticate()
                headers["Authorization"] = f"Bearer {token}"
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_courses(self) -> list[dict]:
        """List courses for the authenticated user."""
        data = await self._api_request("/courses", params={"limit": 100})
        results = data.get("results", []) if isinstance(data, dict) else data

        courses = []
        for course in results:
            courses.append(
                {
                    "id": course.get("id", ""),
                    "name": course.get("name", ""),
                    "courseId": course.get("courseId", ""),
                    "term": (
                        course.get("term", {}).get("name", "")
                        if isinstance(course.get("term"), dict)
                        else ""
                    ),
                }
            )

        self._log.info("blackboard_courses_fetched", count=len(courses))
        return courses

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_assignments(self, course_id: str) -> list[dict]:
        """Get assignments for a specific course."""
        data = await self._api_request(
            f"/courses/{course_id}/contents",
            params={"limit": 100},
        )
        results = data.get("results", []) if isinstance(data, dict) else data

        assignments = []
        for item in results:
            if item.get("contentHandler", {}).get("id") in (
                "resource/x-bb-assignment",
                "resource/x-bb-asmt-test-link",
            ):
                assignments.append(
                    {
                        "id": item.get("id", ""),
                        "name": item.get("title", ""),
                        "due_at": item.get("availability", {})
                        .get("adaptiveRelease", {})
                        .get("end"),
                        "description": item.get("body", ""),
                        "course_id": course_id,
                    }
                )

        self._log.info(
            "blackboard_assignments_fetched",
            course_id=course_id,
            count=len(assignments),
        )
        return assignments

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_grades(self, course_id: str) -> list[dict]:
        """Get grades for a specific course."""
        data = await self._api_request(
            f"/courses/{course_id}/gradebook/columns",
            params={"limit": 100},
        )
        results = data.get("results", []) if isinstance(data, dict) else data

        grades = []
        for col in results:
            grades.append(
                {
                    "column_id": col.get("id", ""),
                    "name": col.get("name", ""),
                    "score": col.get("score", {}).get("possible", 0),
                    "grade_type": col.get("grading", {}).get("type", ""),
                }
            )

        self._log.info("blackboard_grades_fetched", course_id=course_id, count=len(grades))
        return grades

    async def store_assignments(self, course_name: str, assignments: list[dict]) -> int:
        """Store Blackboard assignments in the database."""
        uid = uuid.UUID(self.user_id)
        stored = 0

        for a in assignments:
            external_id = f"blackboard_{a['id']}"
            existing = await self.db.execute(
                select(Assignment).where(Assignment.external_id == external_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            due_at = None
            if a.get("due_at"):
                import contextlib

                with contextlib.suppress(ValueError, AttributeError):
                    due_at = datetime.fromisoformat(str(a["due_at"]).replace("Z", "+00:00"))

            assignment = Assignment(
                user_id=uid,
                platform="blackboard",
                course=course_name,
                title=a["name"],
                due_date=due_at,
                status="pending",
                assignment_type="homework",
                description=a.get("description", "")[:500] if a.get("description") else None,
                external_id=external_id,
            )
            self.db.add(assignment)
            stored += 1

        await self.db.flush()
        return stored

    async def sync(self) -> None:
        """Pull all courses and assignments from Blackboard."""
        courses = await self.get_courses()
        for course in courses:
            assignments = await self.get_assignments(course["id"])
            await self.store_assignments(course["name"], assignments)

        await self._audit(
            action="blackboard_sync",
            resource_type="assignment",
            metadata={"courses": len(courses)},
        )

    async def health_check(self) -> bool:
        """Verify Blackboard credentials are valid."""
        try:
            await self.get_courses()
            return True
        except Exception:
            self._log.warning("blackboard_health_check_failed")
            return False
