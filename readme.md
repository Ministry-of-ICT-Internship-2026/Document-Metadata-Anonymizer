# 🛡️ Document Metadata Anonymizer - Front-End UI

This is a production-ready, high-fidelity UI prototype for the **Document Metadata Anonymizer** tool, built using **Streamlit**. It features batch file uploads, a real-time sidebar configuration menu, a side-by-side Before/After comparison matrix, progress tracking, and batch zip downloading hooks.

---

## 🎨 UI/UX Features Built-In
* **Reactive Metadata Blueprint:** Checking or unchecking sidebar options instantly changes the color-coded comparison badges (Red for marked data, Green for stripped/blank state predictions).
* **Multi-File Processing Flow:** Built specifically to scale and handle single files or entire folders with structural tracking states.

---

## 🚀 Getting Started

### Prerequisites
Make sure you have Python 3.8+ installed on your machine.

### Installation
1. Clone or download this project folder.
2. Open your terminal in the directory containing these files and run:
   ```bash
   pip install -r requirements.txt
   ```

### Running the App
Launch the web interface locally using:
```bash
streamlit run app.py
```

---

## 🛠️ Hand-Off Guide for Backend Developers

The interface code (`app.py`) is modular and clearly split into 4 logical layout sections. To connect your file processing pipelines, look for these variables and injection points inside the file:

### 1. Configuration States (Sidebar)
You can directly query the status of the user's extraction rules using these boolean variables:
* `strip_author` (bool)
* `strip_dates` (bool)
* `strip_geo` (bool)
* `strip_software` (bool)
* `suffix` (str) — e.g., `"_anonymized"`
* `overwrite` (bool) — Determines whether to alter original file names or drop suffixes.

### 2. File Ingestion (Step 1)
The file uploader variable `uploaded_files` returns a **list of BytesIO-like uploaded file objects** from Streamlit. Loop through this list to read raw document/image streams using your target libraries (e.g., `PyPDF2`, `python-docx`, or `openpyxl`).

### 3. File Processing Integration (Step 3)
Locate the block under `# STEP 3: SANITIZATION RUNTIME PROCESSOR`. 
Replace the mock simulation loop (`time.sleep(0.3)`) with your actual python file scrubbing scripts.

### 4. ZIP Packing Hooks (Step 4)
Under `# STEP 4: EXPORT DOWNSTREAM MECHANIC`, look for the `data` parameter in the **Bulk Batch Action** download button:
```python
st.download_button(
    label="⚡ Download All Files as ZIP Bundle",
    data=your_final_zip_bytes_object,  # <-- Connect your zipped archive stream here
    file_name="sanitized_documents_package.zip",
    mime="application/zip",
    use_container_width=True
)
```
