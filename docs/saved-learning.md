# Saved learning and local data

AM now stores generated sessions, selected note excerpts/citations, drafts,
attempts, goals, and review schedules in `.am-data/progress.sqlite3`. This folder
is ignored by Git. Set `AM_DATA_DIR` to use another local directory. It is one
local student profile, not a multi-user account system. Data is not encrypted.

## Resume

Type in the editor and wait for **Draft saved on this computer** before closing
or stopping AM. Drafts save after 600 ms of inactivity. Running tests and changing
exercises wait for pending saves. On startup, the dashboard lists unfinished
sessions; Resume restores their current exercise and draft without generating a
replacement. Save errors remain visible. Conflicting edits from another tab are
rejected rather than overwriting the newer draft; Resume can reload that
version after asking before discarding unsaved changes. Copy your edits first
if you want to keep both versions.

Finishing a session removes it from the unfinished list. Its completed activity
remains in history. A run records an attempt only after grading completes;
infrastructure failures do not create grades. Stop/start leaves saved data intact.
The setup form itself is not an autosaved draft; only generated-session code is.

## Goals, paths, and review

Choose a daily goal from 1 to 20 exercises. The dashboard counts each exercise's
first all-tests-passing run once; repeatedly running the same code cannot inflate
completion counts. Streaks use consecutive days of those completions in the
server computer's local timezone, allowing yesterday's streak until today ends.

Learning paths are topic lists in `learning_paths.py`, not question templates.
Selecting a topic fills the setup form. Choose a language and build a session;
the same AI author/review/execution workflow always generates the question.
Completed topics are marked for the selected language.

A first successful topic is scheduled for tomorrow. Success on a new exercise
on a later day expands the interval through 3, 7, 14, 30, and 60 days. A failing
run resets the interval to one day. Repeated successful runs on the same day do
not expand it. Due topics refill the setup form with their language selected;
they generate new practice, not a replay of a prewritten question. This is a
simple scheduling heuristic, not a calibrated measure of mastery.

## Export and delete

Open **Local data and privacy** on the dashboard:

- Export downloads JSON containing active generated sessions (including reference
  solutions and test data), drafts, and activity. Treat this as private study data.
- Delete clears sessions, drafts, activity, review schedules, and goal settings.
- Optional `.am-diagnostics/` reports and files already exported elsewhere are
  separate and are not deleted by this control.

Export is a readable backup, not an import/migration format yet. For a complete
filesystem backup, stop AM and copy the `.am-data/` folder. The app uses a private
SQLite file and ordinary transactions; do not edit its JSON while AM is running.
