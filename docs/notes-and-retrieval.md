# PDF notes and local retrieval

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
exercise's **Sources used for this question** panel. Relevant material near the
end of a long document is included when it matches the query.

This is local lexical retrieval, not embedding search or web research. There is
no vector database, external API key, or extra model. If a long document has no
matching terms, preparation asks for a matching topic or focused excerpt rather
than pretending to have grounded the question. A source match shows where a
passage came from; it does not prove the model interpreted it correctly.

The original uploaded PDF is not retained. Generated sessions store selected
excerpts/citations, the task, and draft/progress information in the local study
database. Author and reviewer still undergo the same structure and execution
checks after retrieval; the app never falls back to a built-in question bank.
