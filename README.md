# Document Metadata Anonymizer

A client-side tool that strips hidden metadata from PDF, DOCX, and XLSX files without changing how they look — built for Ugandan government MDA (Ministries, Departments and Agencies) staff and any privacy-conscious user who needs to share documents safely.

## The Problem

Public and government documents leak information that never shows up when you open the file: author names, internal usernames, server file paths, tracked-changes history, and even GPS coordinates buried in embedded images. A document can look perfectly clean on screen while its metadata quietly exposes who wrote it, what machine it came from, or where a photo was taken. For government agencies handling sensitive records, that hidden layer is a real security and privacy risk — and most people have no easy way to see it, let alone remove it.

Document Metadata Anonymizer solves this by giving anyone a simple way to inspect a file's hidden metadata, strip it in one click, and confirm the visible content is untouched.

## Trust Model: Everything Stays on Your Machine

This is the single most important thing to know about the tool: **no file is ever uploaded anywhere.** The entire anonymization process — reading metadata, stripping it, writing the cleaned file — runs locally on your computer. Nothing is sent over the network, nothing touches a server, and no internet connection is required to use it. This is what makes the tool safe to use on sensitive or classified government documents: your files never leave your device.

## Supported File Types

| Format | Extension | What gets stripped |
|---|---|---|
| PDF | `.pdf` | Document Info dictionary, XMP metadata |
| Word | `.docx` | Author, company, revision history, comments, embedded image EXIF/GPS data |
| Excel | `.xlsx` | Author, company, calculation chain metadata, embedded image EXIF/GPS data |

## Installation

**Requirements:** Python 3.9 or later

```bash
# 1. Clone or download this repository
git clone <repository-url>
cd document-metadata-anonymizer

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

`requirements.txt` includes: `PyPDF2`, `python-docx`, `openpyxl`, `Pillow`, and `streamlit` (or `tkinter`, which ships with most Python installs, if using the desktop UI build).

## How to Run

**Streamlit (browser-based UI, still fully local):**
```bash
streamlit run app.py
```
This opens the tool in your default browser at `http://localhost:8501`. Nothing here goes to the internet — Streamlit is just rendering the interface locally.

**Tkinter (native desktop UI):**
```bash
python app.py
```

## Usage Walkthrough

1. **Drag a file in.** Drop a PDF, DOCX, or XLSX file onto the upload area (or click to browse).
2. **See the before/after comparison.** The tool automatically detects the file type, reads its current metadata, and displays it side by side with what the file will look like once cleaned — author fields, timestamps, internal paths, embedded GPS data, and more.
3. **Strip and export.** Click "Clean File" to generate a metadata-free copy. The visible content, formatting, and layout are identical to the original — only the hidden metadata is removed.
4. **Save the clean file.** Choose where to save the anonymized copy. Your original file is never modified or deleted.

## Project Architecture

```
UI Layer (Streamlit / Tkinter)
        │
        ▼
   Orchestrator  ── detects file type, routes to the correct module
        │
   ┌────┼────┐
   ▼    ▼    ▼
 PDF   DOCX  XLSX
Stripper Stripper Stripper
(pdf_stripper.py) (docx_stripper.py) (xlsx_stripper.py)
   │    │    │
   └────┴────┘
        ▼
 Before/After metadata comparison shown in UI
```

Each stripper module exposes two functions: `read_metadata()` to extract current metadata, and `strip_metadata()` to produce a cleaned copy.

## Team

| Role | Member |
|---|---|
| Project Manager / Lead Architect | Mwebaza Tony |
| PDF Metadata Engineer (PyPDF2) | Member 2 |
| DOCX Metadata Engineer (python-docx) | Member 3 |
| XLSX/Image Metadata Engineer (openpyxl, Pillow) | Member 4 |
| UI/UX Developer (Streamlit/Tkinter) | Member 5 |
| QA & Security Testing Engineer | Member 6 |
| Documentation & Presentation Lead | Member 7 |

## Project Status

Built over a 4-week sprint: Week 1 (Setup & Design) → Week 2 (Core Modules) → Week 3 (Integration & UI) → Week 4 (QA & Delivery). See the project report for full details on architecture, testing, and results.

## License

Academic project — for coursework submission and demonstration purposes.
