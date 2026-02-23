"""Canvas LMS integration — courses, assignments, grades, announcements."""

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


class CanvasClient(BaseIntegration):
    """Integration client for Canvas LMS REST API.

    Uses a personal access token for authentication. Read-only operations
    for courses, assignments, grades, and announcements.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._api_url = settings.canvas_api_url.rstrip("/")
        self._token = settings.canvas_access_token

    async def _api_request(
        self,
        path: str,
        *,
        params: dict | None = None,
    ) -> list | dict:
        """Make an authenticated GET request to the Canvas API."""
        url = f"{self._api_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}

        async with httpx.AsyncClient(timeout=30) as client:
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
        """List active courses for the authenticated user.

        Returns:
            List of course dicts with id, name, code.
        """
        data = await self._api_request(
            "/courses",
            params={"enrollment_state": "active", "per_page": 100},
        )

        courses = []
        for course in data if isinstance(data, list) else []:
            courses.append(
                {
                    "id": course["id"],
                    "name": course.get("name", ""),
                    "course_code": course.get("course_code", ""),
                    "term": course.get("term", {}).get("name", ""),
                }
            )

        self._log.info("canvas_courses_fetched", count=len(courses))
        return courses

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_assignments(self, course_id: int) -> list[dict]:
        """Get all assignments for a specific course.

        Args:
            course_id: Canvas course ID.

        Returns:
            List of assignment dicts with id, name, due_at, points, etc.
        """
        data = await self._api_request(
            f"/courses/{course_id}/assignments",
            params={"per_page": 100, "order_by": "due_at"},
        )

        assignments = []
        for a in data if isinstance(data, list) else []:
            assignments.append(
                {
                    "id": a["id"],
                    "name": a.get("name", ""),
                    "due_at": a.get("due_at"),
                    "points_possible": a.get("points_possible", 0),
                    "submission_types": a.get("submission_types", []),
                    "description": a.get("description", ""),
                    "html_url": a.get("html_url", ""),
                    "course_id": course_id,
                }
            )

        self._log.info(
            "canvas_assignments_fetched",
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
    async def get_grades(self, course_id: int) -> list[dict]:
        """Get current grades for a specific course.

        Returns:
            List of grade entries with assignment name, score, and grade.
        """
        data = await self._api_request(
            f"/courses/{course_id}/students/submissions",
            params={"student_ids[]": "self", "per_page": 100},
        )

        grades = []
        for sub in data if isinstance(data, list) else []:
            grades.append(
                {
                    "assignment_id": sub.get("assignment_id"),
                    "score": sub.get("score"),
                    "grade": sub.get("grade"),
                    "submitted_at": sub.get("submitted_at"),
                    "workflow_state": sub.get("workflow_state", ""),
                }
            )

        self._log.info("canvas_grades_fetched", course_id=course_id, count=len(grades))
        return grades

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_announcements(self, course_id: int) -> list[dict]:
        """Get recent announcements for a course.

        Returns:
            List of announcement dicts with title, message, posted_at.
        """
        data = await self._api_request(
            "/announcements",
            params={"context_codes[]": f"course_{course_id}", "per_page": 20},
        )

        announcements = []
        for ann in data if isinstance(data, list) else []:
            announcements.append(
                {
                    "id": ann.get("id"),
                    "title": ann.get("title", ""),
                    "message": ann.get("message", ""),
                    "posted_at": ann.get("posted_at"),
                    "author": ann.get("author", {}).get("display_name", ""),
                }
            )

        self._log.info(
            "canvas_announcements_fetched",
            course_id=course_id,
            count=len(announcements),
        )
        return announcements

    async def store_assignments(self, course_name: str, assignments: list[dict]) -> int:
        """Store Canvas assignments in the database.

        Returns:
            Count of new assignments stored.
        """
        uid = uuid.UUID(self.user_id)
        stored = 0

        for a in assignments:
            external_id = f"canvas_{a['id']}"
            existing = await self.db.execute(
                select(Assignment).where(Assignment.external_id == external_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            due_at = None
            if a.get("due_at"):
                import contextlib

                with contextlib.suppress(ValueError, AttributeError):
                    due_at = datetime.fromisoformat(a["due_at"].replace("Z", "+00:00"))

            assignment = Assignment(
                user_id=uid,
                platform="canvas",
                course=course_name,
                title=a["name"],
                due_date=due_at,
                status="pending",
                assignment_type=_infer_type(a.get("submission_types", [])),
                url=a.get("html_url"),
                description=a.get("description", "")[:500] if a.get("description") else None,
                external_id=external_id,
            )
            self.db.add(assignment)
            stored += 1

        await self.db.flush()
        return stored

    async def sync(self) -> None:
        """Pull all courses and assignments from Canvas."""
        courses = await self.get_courses()
        for course in courses:
            assignments = await self.get_assignments(course["id"])
            await self.store_assignments(course["name"], assignments)

        await self._audit(
            action="canvas_sync",
            resource_type="assignment",
            metadata={"courses": len(courses)},
        )

    async def health_check(self) -> bool:
        """Verify Canvas credentials are valid."""
        try:
            await self.get_courses()
            return True
        except Exception:
            self._log.warning("canvas_health_check_failed")
            return False


def _infer_type(submission_types: list[str]) -> str:
    """Infer assignment type from Canvas submission types."""
    if "online_quiz" in submission_types:
        return "quiz"
    if "discussion_topic" in submission_types:
        return "discussion"
    if "online_upload" in submission_types:
        return "upload"
    if "external_tool" in submission_types:
        return "external"
    return "homework"
