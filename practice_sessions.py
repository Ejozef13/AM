"""Bounded, in-memory study sessions using AI-generated, execution-checked exercises."""

from dataclasses import asdict, dataclass, field
import time
import uuid

from study_input import study_input
from note_retrieval import retrieve
from web_retrieval import search_references


@dataclass
class PracticeSession:
    lessons: list
    plan: dict
    planner_label: str
    created: float = field(default_factory=time.monotonic)
    index: int = 0
    attempts: dict = field(default_factory=dict)
    drafts: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    topic: str = ""

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
    def __init__(self, generator, persistence=None):
        if generator is None:
            raise ValueError("An AI exercise generator is required.")
        self.generator = generator
        self.persistence = persistence
        self.sessions = {}
        if persistence:
            for key, value in persistence.load_sessions().items():
                value['attempts'] = {int(k):v for k,v in value.get('attempts',{}).items()}
                value['drafts'] = {int(k):v for k,v in value.get('drafts',{}).items()}
                self.sessions[key] = PracticeSession(**value)

    def prune(self):
        if self.persistence:
            return
        now = time.monotonic()
        for key, session in list(self.sessions.items()):
            if now - session.created > 7200:
                del self.sessions[key]

    def create(self, data):
        self.prune()
        if len(self.sessions) >= 24:
            raise ValueError("Too many open sessions. Finish a session or restart this local app.")
        allowed = tuple(self.generator.runtimes) if self.generator is not None and hasattr(self.generator, 'runtimes') else ('python',)
        topic, notes, count, difficulty = study_input(data, allowed)
        generator = self.generator.for_language(data['language']) if hasattr(self.generator, 'for_language') else self.generator
        context, citations = retrieve(topic, notes)
        web_sources = []
        if data.get('use_web', False):
            generator.progress('AM is retrieving internet reference articles…')
            web_sources = search_references(topic, getattr(generator, 'cancel_event', None))
        generator.web_sources = web_sources
        lessons, plan, label = generator.build(topic, context, difficulty, count)
        key, session = self.publish(lessons, plan, label)
        session.citations, session.topic = citations + web_sources, topic or plan['focus']
        self.save(key)
        return key, session

    def publish(self, lessons, plan, label):
        key = uuid.uuid4().hex
        session = PracticeSession(lessons, plan, label)
        self.sessions[key] = session
        self.save(key)
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
            if self.persistence:
                self.persistence.delete_session(key)
            return {"stage": "summary", "summary": summary}
        self.save(key)
        return self.view(key, session, public_lesson)

    def finish(self, data):
        key, session = self.get(data)
        summary = session.summary()
        del self.sessions[key]
        if self.persistence:
            self.persistence.delete_session(key)
        return {"stage": "summary", "summary": summary}

    def save(self, key):
        if self.persistence:
            self.persistence.save_session(key, asdict(self.sessions[key]))

    def save_draft(self, data):
        key, session = self.get(data)
        source, version = data.get('source'), data.get('version')
        if not isinstance(source, str) or len(source.encode()) > 16000:
            raise ValueError('Draft must be text below 16,000 bytes.')
        previous = session.drafts.get(session.index, {}).get('version', 0)
        if type(version) is not int or version != previous:
            raise ValueError('This draft changed in another tab. Resume the session to load its latest version.')
        session.drafts[session.index] = {'source': source, 'version': previous+1}
        self.save(key)
        return {'version': previous+1}

    def active(self):
        return [{'session_id':key,'title':s.lessons[s.index]['title'],
                 'language':s.lessons[s.index]['language'], 'number':s.index+1, 'total':len(s.lessons)}
                for key,s in self.sessions.items()]

    @staticmethod
    def view(key, session, public_lesson):
        return {"stage": "exercise", "session_id": key, "lesson_index": session.index,
                "number": session.index + 1, "total": len(session.lessons),
                "plan": session.lessons[session.index].get("focus_plan", session.plan),
                "planner_label": session.planner_label,
                "lesson": public_lesson(session.lessons[session.index]),
                "draft": session.drafts.get(session.index, {}).get('source'),
                "draft_version": session.drafts.get(session.index, {}).get('version', 0),
                "citations": session.citations}
