# Architecture — Document Metadata Anonymizer

## 1. Overview

A client-side tool that strips hidden metadata from PDF, DOCX, and XLSX files
without altering their visible layout or content. Everything runs locally —
no file is ever uploaded anywhere. This is the core trust guarantee for
government/MDA users handling sensitive documents.

## 2. Goals

- Strip identifying/leaking metadata (author, server paths, timestamps, GPS)
- Preserve visible layout, formatting, and page/content integrity
- Batch-process multiple files in one pass
- Show a before/after metadata comparison so the user can verify the clean
- Work fully offline, cross-platform (Windows + Linux)

## 3. Non-Goals (MVP)

- OCR or text redaction
- Cloud sync or accounts
- PPTX/image support (stretch goal, not MVP)

## 4. High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                     UI Layer                         │
│         (Streamlit or Tkinter — app/main.py)         │
│  - Drag-and-drop zone                                │
│  - File list + progress                              │
│  - Before/after metadata comparison view              │
└───────────────────────┬───────────────────────────────┘
                         │ file paths / bytes
                         ▼
┌─────────────────────────────────────────────────────┐
│                  Orchestrator                        │
│              (core/orchestrator.py)                  │
│  - Detects file type by extension/magic bytes         │
│  - Routes to the correct stripper module               │
│  - Aggregates before/after metadata for the UI         │
│  - Handles batch queue + error collection              │
└───────┬─────────────┬─────────────┬───────────────────┘
        ▼              ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ pdf_stripper │ │docx_stripper │ │xlsx_stripper │
│  (PyPDF2)    │ │(python-docx) │ │  (openpyxl)  │
└──────────────┘ └──────────────┘ └──────────────┘
```

Each stripper module exposes the same contract so the orchestrator can treat
them interchangeably:

```python
def read_metadata(filepath: str) -> dict: ...
def strip_metadata(filepath: str, output_path: str) -> dict:
    """Returns the metadata that was removed, for the before/after view."""
```

## 5. Module Ownership

| Module | Owner | Library |
|---|---|---|
| `orchestrator.py` | Mwebaza Tony (PM) | — |
| `pdf_stripper.py` | Member 2 | PyPDF2 |
| `docx_stripper.py` | Member 3 | python-docx |
| `xlsx_stripper.py` | Member 4 | openpyxl |
| `image_stripper.py` (stretch) | Member 4 | Pillow |
| `app/main.py` (UI) | Member 5 | Streamlit / Tkinter |
| `tests/` | Member 6 | pytest |
| `docs/`, presentation | Member 7 | — |

## 6. Metadata Fields in Scope

**PDF:** `/Author`, `/Creator`, `/Producer`, `/CreationDate`, `/ModDate`,
`/Title`, custom XMP metadata, embedded attachment paths.

**DOCX:** `core_properties` (author, last_modified_by, company, revision,
timestamps), comments, tracked changes, template path references.

**XLSX:** `core_properties` (creator, lastModifiedBy, company), custom
document properties, defined names referencing server/network paths, hidden
sheets.

**Images (stretch):** EXIF GPS coordinates, device info, original file path.

## 7. Data Flow / Trust Boundary

Everything happens in-process on the user's machine. No network calls in the
core stripping path. This should be called out explicitly in the UI and in
the final report — it's the main selling point for a security-conscious
audience (government MDAs).

## 8. Testing Strategy

- Unit tests per stripper module against sample files with known metadata
- Integrity tests: confirm visible content/layout is byte-identical except
  for metadata fields (diff rendered pages or extracted text before/after)
- Edge cases: corrupted files, password-protected files, very large files,
  files with zero metadata

## 9. Delivery Phases

| Phase | Week | Focus |
|---|---|---|
| 1 | Week 1 | Scope lock, repo setup, architecture, UI wireframes |
| 2 | Week 2 | Build stripper modules in parallel |
| 3 | Week 3 | Integration, batch flow, comparison view |
| 4 | Week 4 | QA, security verification, docs, demo |

## 10. Open Questions

- Do we need to support password-protected PDFs in MVP, or defer?
- Should hidden sheets in XLSX be deleted or just have metadata stripped?
- Packaging: standalone `.exe` (PyInstaller) vs. hosted Streamlit link —
  decide by end of Week 3 based on how the demo will be delivered.
