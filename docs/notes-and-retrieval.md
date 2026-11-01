# Notes, PDF extraction, and optional internet context

The setup form accepts UTF-8 text, Markdown, code files, and text-based PDFs.
Text/code uploads are limited to 800 KB, PDFs to 4 MB, and combined extracted
notes to 200,000 characters. Uploaded code is never executed as a notes file.

PDF extraction uses the local Poppler `pdftotext` executable:

```bash
# Debian / Ubuntu
sudo apt install poppler-utils
# Arch Linux
sudo pacman -S poppler
```

PDFs are processed in temporary files that are removed after extraction. The
extractor limits pages (150), time (15 seconds), CPU, memory, and output file
size. Encrypted/corrupt PDFs and scanned pages with no extractable text get an
explicit error. OCR and slide-format parsing are not included.

## Retrieval

Short notes go directly to the local model. Longer notes are split into
1,000-character chunks, scored against topic terms, and up to eight passages
are selected in document order. The total model context from retrieval is at
most 10,000 characters. Page/section and character references appear in the
exercise's **Reference context for this question** panel. Relevant material near the
end of a long document is included when it matches the query.

This is local lexical retrieval, not embedding search. Optional internet references are separate (below). There is
no vector database, external API key, or extra model. If a long document has no
matching terms, preparation asks for a matching topic or focused excerpt rather
than pretending to have grounded the question. A source match shows where a
passage came from; it does not prove the model interpreted it correctly.

The original uploaded PDF is not retained. Generated sessions store selected
excerpts/citations, the task, and draft/progress information in the local study
database. Author and reviewer still undergo the same structure and execution
checks after retrieval; the app never falls back to a built-in question bank.

## Optional internet references

Enable **Consult internet reference articles** and enter a topic. AM requests up
to three English Wikipedia article introductions through its public HTTPS API,
with at most 1,800 characters per excerpt. Only the topic is transmitted; notes,
student code, and generated answers are not included in the query. The option is
off by default and needs no API key or new Python dependency. These are reference
articles, not a retrieved question bank. The local model still generates every
exercise and passes the same blind review, execution, and bounded repair checks.

Retrieved excerpts are supplied separately from user notes to author, reviewer,
and repair calls as untrusted background. They cannot override instructions or
satisfy the requirement for an original note excerpt. Sources are shown with
links and saved with sessions. Retrieval establishes provenance, not factual
correctness or proof that the model used every excerpt. Wikipedia coverage and
search relevance vary; inspect the sources for your topic.

The client uses only `https://en.wikipedia.org/w/api.php`, refuses redirects,
limits the response to 192 KiB, and applies an eight-second network timeout.
It does not fetch pasted URLs. If access is blocked, unavailable, malformed, or
no usable articles match, preparation stops with an explicit error. Retry with
a narrower topic or disable internet references to practice from notes. There
is no silent fallback and no fixed exercise is served. A stop request prevents
model generation after retrieval; a pending network operation may wait for its
timeout before finishing. Notes-only operation needs no internet connection.
