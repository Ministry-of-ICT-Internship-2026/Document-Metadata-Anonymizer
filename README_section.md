## DOCX Metadata Stripper (`core/docx_stripper.py`)

Word documents carry far more information than what's visible on the page. Every `.docx` file is a ZIP of XML parts, and several of those parts silently record who touched the file and how — even after the "obvious" author fields look clean. This module strips four leak surfaces:

- **Core & extended document properties** (`docProps/core.xml`, `docProps/app.xml`) — author, last-modified-by, company, manager, title, subject, keywords, comments, category, content status, identifier, language, version, revision number, and created/modified/last-printed timestamps. These are the fields most viewers show under "File → Properties," but many are populated automatically from the OS username or organization settings a staff member never typed in themselves.
- **Word comment authorship** (`word/comments.xml`) — reviewer names, initials, and timestamps attached to `w:comment` elements. A document can look fully "clean" in the visible text while its margin comments still name specific reviewers.
- **Tracked-changes authorship** (`word/document.xml`) — `w:ins`, `w:del`, and related `*Change` elements each carry their own `w:author`/`w:date` pair. Even if all changes have been visually accepted, this metadata can persist in the underlying XML and re-identify who edited what.
- **Attached template paths** (`word/settings.xml`) — the `w:attachedTemplate` reference (and its relationship target) can expose an internal file server path or naming convention (e.g. `\\SERVER01\templates\mda_letterhead.dotx`) that has nothing to do with document content but reveals internal infrastructure.

The module clears all of the above while leaving visible text, formatting, images, and page layout untouched — every other XML part in the archive is copied through byte-for-byte, and only the specific attributes/elements that carry identity are modified.
