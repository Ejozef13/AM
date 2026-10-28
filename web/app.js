"use strict";

// Sessions and drafts are saved by the local server, never in localStorage.
const $ = (id) => document.getElementById(id);
let lesson;
let nextHint = 0;
let busy = false;
let submittedSource = null;
let session = null;
let selectedLanguage = "python";
let lastRun = null;
let draftVersion = 0;
let draftTimer;
let draftQueue = Promise.resolve();
let savedSource = null;
async function saveDraft() {
  clearTimeout(draftTimer);
  const current = session;
  const source = $('source').value;
  if (!current) return draftQueue;
  draftQueue = draftQueue.catch(()=>{}).then(async()=>{
    if (session !== current || source === savedSource) return;
    $('draft-status').textContent = 'Saving draft…';
    try {
      const result = await post('/api/draft',{session_id:current.session_id,lesson_index:current.lesson_index,source,version:draftVersion});
      draftVersion=result.version; savedSource=source;
      $('draft-status').textContent = 'Draft saved on this computer.';
    } catch(error) { $('draft-status').textContent = 'Draft NOT saved: '+error.message; throw error; }
  });
  return draftQueue;
}
const languageLabels = {python: "Python", java: "Java", c: "C", cpp: "C++"};
const labels = {compile_error: "Compiler error", passed: "Passed", failed: "Incorrect result", timeout: "Time limit",
  output_limit: "Output limit", syntax_error: "Syntax error", runtime_error: "Runtime error",
  execution_error: "Execution stopped", protocol_error: "Invalid execution response"};

function showError(message = "", details = "", diagnosticUrl = "") {
  $("error").textContent=message; $("error").hidden=!message;
  $("error-details").hidden=!details; $("error-detail-text").textContent=details;
  $("error-report").hidden=diagnosticUrl!=="/api/diagnostic";
}
function setBusy(value) {
  busy = value;
  for (const id of ["run", "reset", "start", "sample", "next-exercise", "finish-session", "another-session", "notes-file", "difficulty", "count", "topic", "web-search"]) $(id).disabled = value;
  $("hint").disabled = value || !lesson || nextHint >= lesson.hint_count;
  $("source").readOnly = value; $("notes").readOnly = value;
  document.querySelectorAll('.language[data-available="true"]').forEach((button) => { button.disabled = value; });
}
async function post(path, data) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) { const error=new Error(result.error || "Request failed."); error.details=result.details || ""; error.diagnosticUrl=result.diagnostic_url || ""; throw error; }
  return result;
}
function addText(parent, tag, text, className = "") {
  const element = document.createElement(tag); element.textContent = text;
  element.className = className; parent.append(element); return element;
}
function sessionFields() { return {session_id: session.session_id, lesson_index: session.lesson_index}; }
function screen(name) {
  $("study-dashboard").hidden = name !== "setup";
  $("setup").hidden = name !== "setup"; $("workspace").hidden = name !== "exercise";
  $("session-bar").hidden = name !== "exercise"; $("session-summary").hidden = name !== "summary";
  document.querySelectorAll("[data-step]").forEach((step) => {
    if (step.dataset.step === name) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
}
async function perform(message, operation) {
  if (busy) return;
  setBusy(true); showError(); $("loading").hidden = false; $("loading").textContent = message;
  try { await operation(); }
  catch (error) { showError(error.message || "Connection failed. Your editor content is still here.", error.details, error.diagnosticUrl); }
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
    session = null; if(typeof refreshDashboard === 'function') refreshDashboard(); return;
  }
  session = view; lesson = view.lesson; nextHint = 0; submittedSource = null; lastRun = null;
  screen("exercise"); $("results").hidden = true; $("hints").replaceChildren();
  $("hint").textContent = "Show first hint";
  $("session-progress").textContent = `EXERCISE ${view.number} OF ${view.total} · ${lesson.difficulty.toUpperCase()}`;
  $("session-focus").textContent = view.plan.focus;
  $("intro-eyebrow").textContent = "ONE SMALL CHALLENGE";
  $("intro-title").textContent = "Find the bug. Understand the fix.";
  $("intro-description").textContent = view.planner_label;
  $("quality-note").textContent = `AI draft · separate ${lesson.quality.distinct_models ? "model" : "review call (same model)"} · two solutions passed ${lesson.test_count} combined tests. These checks can still miss mistakes.`;
  if (lesson.quality.review_test_repairs) {
    $("quality-note").textContent += ` ${lesson.quality.review_test_repairs} reviewer expected value(s) corrected and rechecked.`;
  }
  $("hint-description").textContent = "AI-authored hints checked in a separate review. Reveal one when you need it.";
  $("title").textContent = lesson.title; $("instructions").textContent = lesson.instructions;
  $("constraints").replaceChildren(); $("skills").replaceChildren();
  for (const text of lesson.constraints) addText($("constraints"), "li", text);
  for (const text of lesson.skills) addText($("skills"), "span", text, "skill");
  $("editor-language").textContent = `${languageLabels[lesson.language] || lesson.language} · ${lesson.language === "java" ? "Solution class" : "function submission"}`;
  $("signature-details").hidden = !lesson.required_signature;
  $("required-signature").textContent = lesson.required_signature || "";
  $("signature-help").textContent = lesson.language === "java" ? "Submit a public class named Solution containing this public static method. The runner supplies main." : lesson.language === "c" ? "Submit the function without main. Array parameters use a pointer and length; node and graph parameters use the supplied types described below." : "Submit this free function without main. Standard headers are provided; additional standard includes are allowed.";
  $("structure-help").textContent = lesson.structure_help || "";
  $("source").value = view.draft ?? lesson.starter_code;
  draftVersion=view.draft_version || 0; savedSource=$('source').value;
  $('draft-status').textContent = view.draft === null ? 'Starter ready. Your edits will save locally.' : 'Saved session restored.';
  codeEditor.sync();
  $('retrieval-sources').replaceChildren();
  for(const citation of view.citations || []) {
    addText($('retrieval-sources'),'h3',citation.source);
    if(citation.url) {
      try { const url=new URL(citation.url); if(url.protocol==='https:') {
        const link=addText($('retrieval-sources'),'a',url.href,'source-link'); link.href=url.href; link.target='_blank'; link.rel='noopener noreferrer';
      } } catch(_) { /* A malformed citation never becomes an executable link. */ }
    }
    addText($('retrieval-sources'),'blockquote',citation.excerpt);
  }
  $('retrieval-details').hidden=!(view.citations || []).length;
  $('research-status').textContent=view.research?.warning || (view.research?.status==='retrieved' ? `${view.research.sources.length} web documentation reference(s) retrieved.` : '');
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
    addText(details, "pre", `Input arguments (JSON): ${test.args_json ?? JSON.stringify(test.args)}`);
    if (test.status === "passed" || test.status === "failed") {
      addText(details, "pre", `Expected return: ${test.expected_json ?? JSON.stringify(test.expected)}\nActual return:   ${test.actual_json ?? JSON.stringify(test.actual)}`);
      if (test.input_modified) addText(details, "p", "The input was modified; this lesson forbids that.", "result-message");
    } else { addText(details, test.status === "compile_error" || test.status === "runtime_error" ? "pre" : "p", test.message || "Execution did not return a result.", "result-message"); }
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
    await saveDraft();
    const result = await post("/api/run", {...sessionFields(), source});
    submittedSource = source; renderResults(result);
    if(typeof refreshDashboard === "function") refreshDashboard();
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
      notes: $("notes").value, difficulty: $("difficulty").value, count: Number($("count").value), web_search: $("web-search").checked});
    renderSession(view);
    if(typeof refreshDashboard === "function") refreshDashboard();
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
  $('draft-status').textContent='Unsaved changes…';
  clearTimeout(draftTimer); draftTimer=setTimeout(()=>saveDraft().catch(()=>{}),600);
  if (submittedSource !== null && $("source").value !== submittedSource) $("result-note").textContent = "These results belong to your previous code. Run tests again after editing.";
  else if (submittedSource !== null) $("result-note").textContent = "Results match the code currently in the editor.";
});
$("reset").addEventListener("click", () => {
  if ($("source").value !== lesson.starter_code && !confirm("Replace your current code with the starter?")) return;
  $("source").value = lesson.starter_code; $("results").hidden = true; submittedSource = null; lastRun = null; codeEditor.sync(); $("source").dispatchEvent(new Event("input")); showError();
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
  perform("Opening the next exercise…", async () => { await saveDraft(); renderSession(await post("/api/session/next", sessionFields())); });
});
$("finish-session").addEventListener("click", () => {
  if (!confirm("Finish this session? It will leave the unfinished-session list; completed activity stays saved.")) return;
  perform("Finishing your session…", async () => { await saveDraft(); renderSession(await post("/api/session/finish", sessionFields())); });
});
$("another-session").addEventListener("click", () => {
  screen("setup"); if(typeof refreshDashboard === "function") refreshDashboard(); showError(); $("intro-eyebrow").textContent = "MAKE THE NEXT FEW MINUTES COUNT";
  $("intro-title").textContent = "A little code. A little progress.";
  $("intro-description").textContent = "Pick a language. Bring your notes. Build your debugging skills, one short challenge at a time.";
});
$("notes-file").addEventListener("change", async () => {
  const file = $("notes-file").files[0]; if (!file) return;
  setBusy(true);
  try {
    if (!/\.(txt|md|markdown|py|java|c|cpp|h|hpp|pdf)$/i.test(file.name) || file.size > (/\.pdf$/i.test(file.name)?4194304:800000)) throw new Error("Choose text/code below 800 KB or a PDF below 4 MB.");
    let text;
    if (/\.pdf$/i.test(file.name)) {
      const bytes = new Uint8Array(await file.arrayBuffer()); let binary='';
      for(let offset=0;offset<bytes.length;offset+=8192) binary+=String.fromCharCode(...bytes.subarray(offset,offset+8192));
      text=(await post('/api/notes',{pdf:btoa(binary)})).text;
    } else text = await file.text();
    if (/[\u0000\uFFFD]/.test(text)) throw new Error("The file is not supported UTF-8 text.");
    const combined = [$("notes").value.trim(), text.trim()].filter(Boolean).join("\n\n");
    if (combined.length > 200000) throw new Error("Combined notes exceed 200,000 characters. Use a shorter section.");
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
    const button = addText($("languages"), "button", language.label + (language.available ? "" : " · setup needed"), "language");
    button.type = "button"; button.disabled = !language.available; button.title = language.disabled_reason || "";
    button.dataset.language = language.id;
    button.dataset.available = String(language.available); button.setAttribute("aria-pressed", String(language.id === selectedLanguage));
    button.addEventListener("click", () => {
      selectedLanguage = language.id;
      $("planner-label").textContent = setup.planner_label.replace(/^AI-authored Python exercises/, `AI-authored ${language.label} exercises`);
      document.querySelectorAll(".language").forEach((other) => { other.setAttribute("aria-pressed", "false"); });
      button.setAttribute("aria-pressed", "true");
      if(typeof refreshDashboard === "function") refreshDashboard();
    });
  }
  $("mode-title").textContent = "AI-GENERATED PRACTICE";
  $("family-list").textContent = "Questions built around your topic and notes";
  $("mode-description").textContent = "AM generates a fresh question from your topic, notes, and optional web references. A separate review solves it; both programs run against combined tests. Inconsistent expectations need explicit verification before using executed results.";
  const missingRuntime = setup.mode === "ai-generated" && setup.languages.some((language) => !language.available);
  $("runtime-setup").hidden = !missingRuntime;
  $("runtime-setup").textContent = missingRuntime ? "To enable Java, C, and C++: run sudo -v, then python tools/setup_compiled_runtime.py in your terminal, and restart this app." : "";
  $("planner-label").textContent = setup.planner_label;
  $("loading").hidden = true; screen("setup"); setBusy(false);
}).catch((error) => { $("loading").hidden = true; showError(error.message); });

window.addEventListener('beforeunload',event=>{
  if(session && $('source').value!==savedSource) { event.preventDefault(); event.returnValue=''; }
});
