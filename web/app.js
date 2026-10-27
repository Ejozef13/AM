"use strict";

// State lives in this tab. No uploads, source, or progress go into localStorage.
const $ = (id) => document.getElementById(id);
let lesson;
let nextHint = 0;
let busy = false;
let submittedSource = null;
let session = null;
let selectedLanguage = "python";
let lastRun = null;
let generationMode = false;
const labels = {passed: "Passed", failed: "Incorrect result", timeout: "Time limit",
  output_limit: "Output limit", syntax_error: "Syntax error", runtime_error: "Runtime error",
  execution_error: "Execution stopped", protocol_error: "Invalid execution response"};

function showError(message = "") { $("error").textContent = message; $("error").hidden = !message; }
function setBusy(value) {
  busy = value;
  for (const id of ["run", "reset", "start", "sample", "next-exercise", "finish-session", "another-session", "notes-file", "difficulty", "count", "topic"]) $(id).disabled = value;
  $("hint").disabled = value || !lesson || nextHint >= lesson.hint_count;
  $("source").readOnly = value; $("notes").readOnly = value;
  document.querySelectorAll('.language[data-available="true"]').forEach((button) => { button.disabled = value; });
}
async function post(path, data) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed.");
  return result;
}
function addText(parent, tag, text, className = "") {
  const element = document.createElement(tag); element.textContent = text;
  element.className = className; parent.append(element); return element;
}
function sessionFields() { return {session_id: session.session_id, lesson_index: session.lesson_index}; }
function screen(name) {
  $("setup").hidden = name !== "setup"; $("workspace").hidden = name !== "exercise";
  $("session-bar").hidden = name !== "exercise"; $("session-summary").hidden = name !== "summary";
}
async function perform(message, operation) {
  if (busy) return;
  setBusy(true); showError(); $("loading").hidden = false; $("loading").textContent = message;
  try { await operation(); }
  catch (error) { showError(error.message || "Connection failed. Your editor content is still here."); }
  finally { $("loading").hidden = true; setBusy(false); }
}
function renderSession(view) {
  if (view.stage === "summary") {
    const summary = view.summary; screen("summary");
    $("summary-count").textContent = `${summary.completed} of ${summary.total} exercises passed every test on their latest run. This is session feedback, not a measure of mastery.`;
    $("summary-items").replaceChildren();
    for (const item of summary.items) {
      const section = document.createElement("section"); section.className = "review-item";
      addText(section, "h3", item.title);
      addText(section, "p", item.passed === null ? "Not attempted" : `${item.passed}/${item.total} tests passed · ${item.attempts} attempt(s)`);
      $("summary-items").append(section);
    }
    session = null; return;
  }
  session = view; lesson = view.lesson; nextHint = 0; submittedSource = null; lastRun = null;
  screen("exercise"); $("results").hidden = true; $("hints").replaceChildren();
  $("hint").textContent = "Show first hint";
  $("session-progress").textContent = `EXERCISE ${view.number} OF ${view.total} · ${lesson.difficulty.toUpperCase()}`;
  $("session-focus").textContent = view.plan.focus;
  $("intro-eyebrow").textContent = "ONE SMALL CHALLENGE";
  $("intro-title").textContent = "Find the bug. Understand the fix.";
  $("intro-description").textContent = view.planner_label;
  const generated = lesson.quality && lesson.quality.source === "ai-generated";
  $("quality-note").textContent = generated ? `AI draft · separate ${lesson.quality.distinct_models ? "model" : "review call (same model)"} · two solutions passed ${lesson.test_count} combined tests. These checks can still miss mistakes.` : "Reviewed template exercise.";
  if (generated && lesson.quality.review_test_repairs) {
    $("quality-note").textContent += ` ${lesson.quality.review_test_repairs} reviewer expected value(s) corrected and rechecked.`;
  }
  $("hint-description").textContent = generated ? "AI-authored hints checked in a separate review. Reveal one when you need it." : "Hints are reviewed lesson content. Reveal one when you need it.";
  $("title").textContent = lesson.title; $("instructions").textContent = lesson.instructions;
  $("constraints").replaceChildren(); $("skills").replaceChildren();
  for (const text of lesson.constraints) addText($("constraints"), "li", text);
  for (const text of lesson.skills) addText($("skills"), "span", text, "skill");
  $("source").value = lesson.starter_code;
  $("focus-evidence").hidden = false; $("focus-evidence").open = false;
  $("focus-reason").textContent = view.plan.reason;
  $("notes-quote").textContent = view.plan.notes_quote || "Selected from your topic; no notes were supplied.";
  $("next-exercise").textContent = view.number === view.total ? "See session summary →" : "Next exercise →";
}
function renderResults(result) {
  lastRun = result; $("results").hidden = false;
  const allPassed = result.passed === result.total;
  $("result-title").textContent = allPassed ? `All ${result.total} tests passed. You found the fix.` : `${result.passed} of ${result.total} tests passed`;
  $("result-title").className = allPassed ? "success" : "failure";
  $("result-note").textContent = allPassed ? "Your solution satisfies these reviewed cases. Inspect the requirements too." : "Open a failed case, inspect the evidence, and try another change.";
  $("test-list").replaceChildren();
  for (const test of result.results) {
    const details = document.createElement("details"); details.className = "test"; details.open = test.status !== "passed";
    addText(details, "summary", `${labels[test.status] || test.status} · ${test.name}`, test.status === "passed" ? "pass" : "fail");
    if (test.status === "passed" || test.status === "failed") {
      addText(details, "pre", `Expected return: ${JSON.stringify(test.expected)}\nActual return:   ${JSON.stringify(test.actual)}`);
      if (test.input_modified) addText(details, "p", "The input was modified; this lesson forbids that.", "result-message");
    } else { addText(details, "p", test.message || "Execution did not return a result.", "result-message"); }
    if (test.output) addText(details, "pre", "Printed output:\n" + test.output);
    $("test-list").append(details);
  }
}
async function runTests() {
  if (busy || !session) return;
  const source = $("source").value;
  if (!source.trim()) { showError("Enter your solution first."); return; }
  await perform(`Running ${lesson.test_count} isolated tests…`, async () => {
    $("results").hidden = true;
    const result = await post("/api/run", {...sessionFields(), source});
    submittedSource = source; renderResults(result);
  });
}
$("setup-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!$("topic").value.trim() && !$("notes").value.trim()) { showError("Add a topic or paste your notes first."); return; }
  perform("Preparing your exercise. AI generation and execution checks can take several minutes…", async () => {
    const timer = setInterval(async () => {
      try {
        const response = await fetch("/api/progress");
        if (response.ok) {
          const progress = await response.json();
          if (progress.busy) $("loading").textContent = progress.message;
        }
      } catch (_) { /* The session request reports connection failures. */ }
    }, 2000);
    try {
    const view = await post("/api/session", {language: selectedLanguage, topic: $("topic").value,
      notes: $("notes").value, difficulty: $("difficulty").value, count: Number($("count").value)});
    renderSession(view);
    } finally { clearInterval(timer); }
  });
});
$("run").addEventListener("click", runTests);
$("source").addEventListener("keydown", (event) => {
  if (event.key === "Tab" && !busy) {
    event.preventDefault(); const editor = $("source");
    editor.setRangeText("    ", editor.selectionStart, editor.selectionEnd, "end"); editor.dispatchEvent(new Event("input"));
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); runTests(); }
});
$("source").addEventListener("input", () => {
  if (submittedSource !== null && $("source").value !== submittedSource) $("result-note").textContent = "These results belong to your previous code. Run tests again after editing.";
  else if (submittedSource !== null) $("result-note").textContent = "Results match the code currently in the editor.";
});
$("reset").addEventListener("click", () => {
  if ($("source").value !== lesson.starter_code && !confirm("Replace your current code with the starter?")) return;
  $("source").value = lesson.starter_code; $("results").hidden = true; submittedSource = null; lastRun = null; showError();
});
$("hint").addEventListener("click", () => {
  if (busy || !session || nextHint >= lesson.hint_count) return;
  perform("Opening a reviewed hint…", async () => {
    const result = await post("/api/hint", {...sessionFields(), index: nextHint});
    addText($("hints"), "li", result.hint); nextHint += 1;
    $("hint").textContent = nextHint >= lesson.hint_count ? "All hints revealed" : "Show next hint";
  });
});
$("next-exercise").addEventListener("click", () => {
  const currentPassed = lastRun && lastRun.passed === lastRun.total && $("source").value === submittedSource;
  if (!currentPassed && !confirm("Move on? The summary will retain this exercise's latest test result, if any.")) return;
  perform("Opening the next exercise…", async () => { renderSession(await post("/api/session/next", sessionFields())); });
});
$("finish-session").addEventListener("click", () => {
  if (!confirm("Finish this session? Your current editor draft is not saved.")) return;
  perform("Finishing your session…", async () => { renderSession(await post("/api/session/finish", sessionFields())); });
});
$("another-session").addEventListener("click", () => {
  screen("setup"); showError(); $("intro-eyebrow").textContent = "MAKE THE NEXT FEW MINUTES COUNT";
  $("intro-title").textContent = "What are we studying today?";
  $("intro-description").textContent = "Bring a topic or a few notes. Turn them into a short, focused coding session.";
});
$("notes-file").addEventListener("change", async () => {
  const file = $("notes-file").files[0]; if (!file) return;
  setBusy(true);
  try {
    if (!/\.(txt|md|markdown|py|java|c|cpp|h|hpp)$/i.test(file.name) || file.size > 48000) throw new Error("Choose a UTF-8 text, Markdown, or code file under 48 KB. PDFs and slides are not supported yet.");
    const text = await file.text();
    if (/[\u0000\uFFFD]/.test(text)) throw new Error("The file is not supported UTF-8 text.");
    const combined = [$("notes").value.trim(), text.trim()].filter(Boolean).join("\n\n");
    if (combined.length > 12000) throw new Error("Combined notes exceed 12,000 characters. Use a shorter excerpt.");
    $("notes").value = combined; $("file-status").textContent = `Added ${file.name}`; showError();
  } catch (error) { showError(error.message); }
  finally { $("notes-file").value = ""; setBusy(false); }
});
$("sample").addEventListener("click", () => {
  $("topic").value = "Counting with loops";
  $("notes").value = "A counter starts at zero. Visit every element of a list, and increment the counter only when a condition matches. Return the count after the loop finishes. Empty lists have zero matches.";
  $("file-status").textContent = "";
});
fetch("/api/setup").then(async (response) => {
  if (!response.ok) throw new Error("Could not load practice options.");
  const setup = await response.json();
  for (const language of setup.languages) {
    const button = addText($("languages"), "button", language.label + (language.available ? "" : " · planned"), "language");
    button.type = "button"; button.disabled = !language.available;
    button.dataset.available = String(language.available); button.setAttribute("aria-pressed", String(language.id === selectedLanguage));
    button.addEventListener("click", () => {
      selectedLanguage = language.id;
      document.querySelectorAll(".language").forEach((other) => { other.setAttribute("aria-pressed", "false"); });
      button.setAttribute("aria-pressed", "true");
    });
  }
  generationMode = setup.mode === "ai-generated";
  $("mode-title").textContent = generationMode ? "AI-GENERATED PRACTICE · PYTHON FIRST" : "REVIEWED TEMPLATE PRACTICE";
  $("family-list").textContent = generationMode ? "Questions built around your topic and notes" : setup.families.map((family) => family.title).join(" · ");
  $("mode-description").textContent = generationMode ? "AM drafts a debugging question. A separate review solves it independently, then both solutions must pass the combined tests. Start with one exercise. Notes guide the question; web research is not enabled." : "Available families use reviewed generators with execution checks. Other topics need AI-generated mode.";
  $("planner-label").textContent = setup.planner_label;
  $("loading").hidden = true; screen("setup"); setBusy(false);
}).catch((error) => { $("loading").hidden = true; showError(error.message); });
