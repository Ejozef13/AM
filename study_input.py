"""Validate student inputs without selecting or supplying questions."""

LEVELS = ("introductory", "standard", "challenging")

LANGUAGES = [
    {"id": "python", "label": "Python", "available": True},
    {"id": "java", "label": "Java", "available": False},
    {"id": "c", "label": "C", "available": False},
    {"id": "cpp", "label": "C++", "available": False},
]


def study_input(data, allowed_languages=('python',)):
    if data.get("language") not in allowed_languages:
        raise ValueError("This language is not available in the current mode. Set up its runtime first.")
    topic, notes = data.get("topic", ""), data.get("notes", "")
    if not isinstance(topic, str) or len(topic) > 160:
        raise ValueError("Keep the topic below 160 characters.")
    if not isinstance(notes, str) or len(notes) > 200000:
        raise ValueError("Keep notes below 200,000 characters.")
    if not topic.strip() and not notes.strip():
        raise ValueError("Add a topic or some notes to guide your session.")
    count, difficulty = data.get("count", 3), data.get("difficulty", "standard")
    if type(count) is not int or not 1 <= count <= 5:
        raise ValueError("Choose one to five exercises.")
    if difficulty not in LEVELS:
        raise ValueError("Choose a listed difficulty.")
    return topic.strip(), notes.strip(), count, difficulty

