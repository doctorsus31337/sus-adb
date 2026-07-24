"""Local-only educational courses, catalog state, and progress persistence."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Lesson:
    lesson_id: str
    title: str
    explanation: str
    prerequisites: tuple[str, ...]
    synthetic_example: str
    optional_practice: str
    expected_result: str
    hints: tuple[str, ...]
    validation: str

    def __post_init__(self):
        for field_name in (
            "lesson_id", "title", "explanation", "synthetic_example",
            "optional_practice", "expected_result", "validation",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"Lesson {field_name} must not be empty.")
        object.__setattr__(self, "prerequisites", tuple(self.prerequisites))
        object.__setattr__(self, "hints", tuple(self.hints))


@dataclass(frozen=True, slots=True)
class Course:
    course_id: str
    plugin_id: str
    title: str
    description: str
    lessons: tuple[Lesson, ...]
    synthetic_only: bool = True
    device_actions: bool = False

    def __post_init__(self):
        object.__setattr__(self, "lessons", tuple(self.lessons))
        identifiers = [lesson.lesson_id for lesson in self.lessons]
        if not self.course_id or not self.plugin_id or not self.title:
            raise ValueError("Course identity and title are required.")
        if not self.lessons or len(identifiers) != len(set(identifiers)):
            raise ValueError("Courses require unique lessons.")
        if self.device_actions:
            raise ValueError("Learning Center courses may not perform device actions.")


@dataclass(frozen=True, slots=True)
class EducationalAddon:
    plugin_id: str
    name: str
    version: str
    installed: bool
    enabled: bool
    loaded: bool
    lesson_count: int = 0


@dataclass(frozen=True, slots=True)
class LearningProgress:
    completed: tuple[str, ...] = ()
    bookmarks: tuple[str, ...] = ()
    exercises: tuple[str, ...] = ()


class LearningProgressStore:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()

    def load(self) -> dict[str, LearningProgress]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {}
            result = {}
            for course_id, value in raw.items():
                if not isinstance(course_id, str) or not isinstance(value, dict):
                    continue
                result[course_id] = LearningProgress(
                    tuple(sorted(set(map(str, value.get("completed", ()))))),
                    tuple(sorted(set(map(str, value.get("bookmarks", ()))))),
                    tuple(sorted(set(map(str, value.get("exercises", ()))))),
                )
            return result
        except (OSError, ValueError, TypeError):
            return {}

    def save(self, progress: dict[str, LearningProgress]) -> bool:
        data = {
            course_id: {
                "completed": list(value.completed),
                "bookmarks": list(value.bookmarks),
                "exercises": list(value.exercises),
            }
            for course_id, value in sorted(progress.items())
        }
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix="learning-", suffix=".tmp", dir=self.path.parent
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            return True
        except OSError:
            if temporary:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass
            return False


class LearningCenterService:
    def __init__(self, plugin_manager, registry, progress_store):
        self.plugin_manager = plugin_manager
        self.registry = registry
        self.progress_store = progress_store
        self.progress = progress_store.load()

    def courses(self) -> tuple[Course, ...]:
        courses = []
        for contribution in self.registry.list("learning-course"):
            try:
                course = contribution.factory(None) if contribution.factory else None
            except Exception:
                continue
            if (
                isinstance(course, Course)
                and course.plugin_id == contribution.plugin_id
                and not course.device_actions
            ):
                courses.append(course)
        return tuple(sorted(courses, key=lambda value: value.title.casefold()))

    def educational_addons(self) -> tuple[EducationalAddon, ...]:
        loaded = {
            contribution.plugin_id
            for contribution in self.registry.list("learning-course")
        }
        course_counts = {
            course.plugin_id: len(course.lessons) for course in self.courses()
        }
        items = []
        for item in self.plugin_manager.official():
            declarations = item.manifest.contributed_components
            if not any(
                value.contribution_type == "learning-course"
                for value in declarations
            ):
                continue
            record = self.plugin_manager.records.get(item.manifest.plugin_id)
            enabled = bool(record and record[2].enabled)
            items.append(EducationalAddon(
                item.manifest.plugin_id,
                item.manifest.name,
                item.manifest.version,
                item.installed,
                enabled,
                item.manifest.plugin_id in loaded,
                course_counts.get(item.manifest.plugin_id, 0),
            ))
        return tuple(sorted(items, key=lambda value: value.name.casefold()))

    def course_progress(self, course_id) -> LearningProgress:
        return self.progress.get(course_id, LearningProgress())

    def mark_complete(self, course: Course, lesson: Lesson, complete=True):
        return self._update(course, lesson, "completed", complete)

    def bookmark(self, course: Course, lesson: Lesson, bookmarked=True):
        return self._update(course, lesson, "bookmarks", bookmarked)

    def record_exercise(self, course: Course, lesson: Lesson):
        return self._update(course, lesson, "exercises", True)

    def _update(self, course, lesson, field, value):
        if lesson not in course.lessons:
            return False
        current = self.course_progress(course.course_id)
        values = {
            "completed": set(current.completed),
            "bookmarks": set(current.bookmarks),
            "exercises": set(current.exercises),
        }
        key = lesson.lesson_id
        (values[field].add if value else values[field].discard)(key)
        self.progress[course.course_id] = LearningProgress(
            tuple(sorted(values["completed"])),
            tuple(sorted(values["bookmarks"])),
            tuple(sorted(values["exercises"])),
        )
        return self.progress_store.save(self.progress)
