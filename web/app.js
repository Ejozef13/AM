"use strict";

// Only the lesson's public fields enter the browser. Code is never evaluated here.
const $ = (id) => document.getElementById(id);
let lesson;
let nextHint = 0;
let busy = false;
let submittedSource = null;
const labels = {passed: "Passed", failed: "Incorrect result", timeout: "Time limit",
  output_limit: "Output limit", syntax_error: "Syntax error", runtime_error: "Runtime error",
  execution_error: "Execution stopped", protocol_error: "Invalid execution response"};

function showError(message = "") { $("error").textContent = message; $("error").hidden = !message; }
function setBusy(value) {
  busy = value; $("run").disabled = value; $("reset").disabled = value;
  $("hint").disabled = value || nextHint >= lesson.hint_count;
  $("source").readOnly = value;
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
function renderResults(result) {
  $("results").hidden = false;
  const allPassed = result.passed === result.total;
  $("result-title").textContent = allPassed ? `All ${result.total} tests passed. You found the fix.` : `${result.passed} of ${result.total} tests passed`;
  $("result-title").className = allPassed ? "success" : "failure";
  $("result-note").textContent = allPassed ? "Your solution satisfies these reviewed cases. Inspect the requirements too." : "Open a failed case, inspect the evidence, and try another change.";
  $("test-list").replaceChildren();
  for (const test of result.results) {
    const details = document.createElement("details"); details.className = "test";
    details.open = test.status !== "passed";
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
  if (busy || !lesson) return;
  const source = $("source").value;
  if (!source.trim()) { showError("Enter your solution first."); return; }
  setBusy(true); showError(); $("results").hidden = true;
  $("activity").textContent = `Running ${lesson.test_count} isolated tests…`;
  try {
    const result = await post("/api/run", {source});
    submittedSource = source; renderResults(result);
  } catch (error) { showError(error.message || "Connection failed. Your code is still in the editor."); }
  finally { $("activity").textContent = ""; setBusy(false); }
}
$("run").addEventListener("click", runTests);
$("source").addEventListener("keydown", (event) => {
  if (event.key === "Tab" && !busy) {
    event.preventDefault(); const editor = $("source");
    editor.setRangeText("    ", editor.selectionStart, editor.selectionEnd, "end");
    editor.dispatchEvent(new Event("input"));
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); runTests(); }
});
$("source").addEventListener("input", () => {
  if (submittedSource !== null && $("source").value !== submittedSource) {
    $("result-note").textContent = "These results belong to your previous code. Run tests again after editing.";
  } else if (submittedSource !== null) {
    $("result-note").textContent = "Results match the code currently in the editor.";
  }
});
$("reset").addEventListener("click", () => {
  if ($("source").value !== lesson.starter_code && !confirm("Replace your current code with the starter?")) return;
  $("source").value = lesson.starter_code; $("results").hidden = true; submittedSource = null; showError();
});
$("hint").addEventListener("click", async () => {
  if (busy || nextHint >= lesson.hint_count) return;
  setBusy(true); showError();
  try {
    const result = await post("/api/hint", {index: nextHint});
    addText($("hints"), "li", result.hint); nextHint += 1;
    $("hint").textContent = nextHint >= lesson.hint_count ? "All hints revealed" : "Show next hint";
  } catch (error) { showError(error.message); }
  finally { setBusy(false); }
});
fetch("/api/lesson").then(async (response) => {
  if (!response.ok) throw new Error("Could not load the lesson.");
  lesson = await response.json();
  $("title").textContent = lesson.title; $("instructions").textContent = lesson.instructions;
  for (const text of lesson.constraints) addText($("constraints"), "li", text);
  for (const text of lesson.skills) addText($("skills"), "span", text, "skill");
  $("source").value = lesson.starter_code;
  $("loading").hidden = true; $("workspace").hidden = false; setBusy(false);
}).catch((error) => { $("loading").hidden = true; showError(error.message); });
