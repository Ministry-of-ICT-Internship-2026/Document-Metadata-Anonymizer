# Demo Video Script — Document Metadata Anonymizer
**Total runtime: ~2:45** | Screen recording with voiceover, no editing required if followed as timed beats.

**Before recording:** have one test file ready on the desktop with known, deliberately fake metadata seeded in — e.g. a DOCX or PDF with author name "J. Placeholder", a fabricated file path in a custom property, and a photo with dummy GPS coordinates embedded. This makes the "after" comparison provably clean rather than relying on whatever metadata a random file happens to have.

---

### 0:00–0:15 — Intro
**Screen:** App closed, clean desktop.
**Voiceover:** "This is the Document Metadata Anonymizer — a tool that strips hidden metadata from PDF, DOCX, and XLSX files without changing how they look, and without ever sending your files anywhere. Everything you're about to see runs entirely on this machine."

### 0:15–0:30 — Launch the app
**Screen:** Launch the app (`streamlit run app.py` or double-click the desktop build). Show the interface loading.
**Voiceover:** "Here's the tool starting up. No login, no internet connection required — it's a local application from the moment it opens."

### 0:30–0:55 — Drag the file in
**Screen:** Drag the pre-prepared test file (with seeded fake metadata) onto the upload area.
**Voiceover:** "I'll drag in a file that already has some fake but realistic metadata planted in it — a placeholder author name, a made-up internal file path, and a photo with dummy GPS coordinates. The tool automatically detects the file type and reads what's hidden inside."

### 0:55–1:35 — Show the before/after comparison
**Screen:** Point out each field in the before/after metadata panel: author, file path, timestamps, GPS data.
**Voiceover:** "Here's the before-and-after view. On the left, you can see everything currently embedded in the file — the author field, the internal path, the GPS tag on the embedded photo. On the right is exactly what will remain once we clean it: nothing. This comparison is shown before any file is modified, so nothing happens silently — you always see exactly what's about to be removed."

### 1:35–1:55 — Strip and export
**Screen:** Click "Clean File," choose a save location, confirm export completes.
**Voiceover:** "One click strips the metadata and generates a cleaned copy — the original file is left untouched. I'll save it right here on the desktop."

### 1:55–2:25 — Reopen the cleaned file to prove it
**Screen:** Open the cleaned file in its native viewer (Word/Adobe/Excel) side by side with the original. Then re-run the tool's metadata reader (or right-click → Properties) on the cleaned file to show empty/default fields.
**Voiceover:** "First, notice the layout, text, and formatting are completely unchanged — the tool never touches visible content. Now let's check the metadata again: the author field, the file path, the GPS tag — all gone. The document looks identical; the hidden layer is empty."

### 2:25–2:45 — Closing
**Screen:** Return to the app's main screen.
**Voiceover:** "That's the full workflow: drag a file in, see exactly what's hidden, strip it in one click, and confirm nothing was left behind — all without a single byte ever leaving this machine. Thanks for watching."

---

## Recording notes
- Keep the mouse movements deliberate and slow enough for viewers to follow each click.
- If recording a live demo instead of a video, these beats double as your speaker cue cards — the timings can flex to fit Q&A.
- Have a backup pre-recorded clip of steps 0:55–2:25 in case the live before/after comparison misbehaves during a live presentation.
