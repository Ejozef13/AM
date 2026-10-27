"""Bounded, in-memory study sessions using reviewed exercise generators."""

from dataclasses import dataclass, field
import secrets
import time
import uuid

from code_runner import RunnerError, grade_case
from exercise_families import generate_lesson
from practice_planner import study_input


@dataclass
class PracticeSession:
    lessons: list
    plan: dict
    planner_label: str
    created: float = field(default_factory=time.monotonic)
    index: int = 0
    attempts: dict = field(default_factory=dict)

    def summary(self):
        items = []
        for index, lesson in enumerate(self.lessons):
            attempt = self.attempts.get(index)
            items.append({"title": lesson["title"], "attempts": attempt["attempts"] if attempt else 0,
                          "passed": attempt["passed"] if attempt else None,
                          "total": len(lesson["tests"])})
        return {"items": items, "completed": sum(item["passed"] == item["total"] for item in items),
                "total": len(items), "focus": self.plan["focus"]}


class SessionStore:
    def __init__(self, planner, runner, generator=None):
        self.planner, self.runner = planner, runner
        self.generator = generator
        self.sessions = {}

    def prune(self):
        now = time.monotonic()
        for key, session in list(self.sessions.items()):
            if now - session.created > 7200:
                del self.sessions[key]

    def create(self, data):
        self.prune()
        if len(self.sessions) >= 24:
            raise ValueError("Too many open sessions. Finish a session or restart this local app.")
        topic, notes, count, difficulty = study_input(data)
        if self.generator is not None:
            lessons, plan, label = self.generator.build(topic, notes, difficulty, count)
            return self.publish(lessons, plan, label)
        plan = self.planner.plan(topic, notes)
        lessons = [generate_lesson(plan["family"], difficulty, secrets.randbits(32)) for _ in range(count)]
        # Validate actual generated artifacts with the same execution boundary used
        # by students. Do not publish a variant with a broken reference or inert bug.
        for lesson in lessons:
            for case in lesson["tests"]:
                result = grade_case(self.runner, lesson["reference_solution"], lesson["entrypoint"], case, True)
                if result["status"] != "passed":
                    raise RunnerError("A generated reference did not pass. No session was published.")
            regression = grade_case(self.runner, lesson["starter_code"], lesson["entrypoint"], lesson["tests"][0], True)
            if regression["status"] != "failed":
                raise RunnerError("The intended starter bug was not detected. No session was published.")
        return self.publish(lessons, plan, self.planner.label)

    def publish(self, lessons, plan, label):
        key = uuid.uuid4().hex
        session = PracticeSession(lessons, plan, label)
        self.sessions[key] = session
        return key, session

    def get(self, data):
        self.prune()
        key = data.get("session_id")
        if not isinstance(key, str) or key not in self.sessions:
            raise ValueError("Session ended or expired. Start a new study session.")
        session = self.sessions[key]
        index = data.get("lesson_index")
        if type(index) is not int or index != session.index:
            raise ValueError("This exercise is no longer current. Start a fresh session if the page is stale.")
        return key, session

    def next(self, data, public_lesson):
        key, session = self.get(data)
        session.index += 1
        if session.index == len(session.lessons):
            summary = session.summary()
            del self.sessions[key]
            return {"stage": "summary", "summary": summary}
        return self.view(key, session, public_lesson)

    def finish(self, data):
        key, session = self.get(data)
        summary = session.summary()
        del self.sessions[key]
        return {"stage": "summary", "summary": summary}

    @staticmethod
    def view(key, session, public_lesson):
        return {"stage": "exercise", "session_id": key, "lesson_index": session.index,
                "number": session.index + 1, "total": len(session.lessons),
                "plan": session.lessons[session.index].get("focus_plan", session.plan),
                "planner_label": session.planner_label,
                "lesson": public_lesson(session.lessons[session.index])}
