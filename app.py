from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from core.orchestrator import (
    create_batch_zip,
    process_batch,
    process_single,
    read_metadata,
)

st.set_page_config(
    page_title="Metadata Purge - Enterprise Anonymizer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.divider()
    st.markdown("### 🛡️ Core Data Settings")
    st.caption("Fields shown in the comparison view.")

    st.markdown("**Show Metadata Categories:**")
    show_author = st.checkbox("Author / Creator", value=True)
    show_dates = st.checkbox("Timestamps (Creation/Modification)", value=True)
    show_geo = st.checkbox("GPS & Location Data", value=True)
    show_software = st.checkbox("Software & Hardware Footprints", value=True)

    st.divider()
    st.markdown("**Output Preferences:**")
    suffix = st.text_input("Clean File Suffix", value="_anonymized")
    overwrite = st.toggle("Overwrite original names in ZIP", value=False)

    st.divider()
    st.caption("🔒 Everything runs locally. No files ever leave your machine.")

bg_color = "#F8FAFC"
card_bg = "#FFFFFF"
text_color = "#0F172A"
border_color = "#E2E8F0"
sub_text = "#64748B"

st.markdown(f"""
<style>
.stApp {{ background-color: {bg_color} !important; color: {text_color} !important; }}
h1, h2, h3, h4, h5, p, span, label {{ color: {text_color} !important; }}
.stMarkdown p {{ color: {text_color} !important; }}
.compare-card {{
    background-color: {card_bg};
    border: 1px solid {border_color};
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    min-height: 250px;
}}
.danger-tag {{ color: #EF4444; font-weight: bold; background: rgba(239,68,68,0.15); padding: 2px 6px; border-radius: 4px; }}
.success-tag {{ color: #10B981; font-weight: bold; background: rgba(16,185,129,0.15); padding: 2px 6px; border-radius: 4px; }}
.muted-text {{ color: {sub_text} !important; font-size: 0.85rem; }}
</style>
""", unsafe_allow_html=True)

if "processed" not in st.session_state:
    st.session_state.processed = False
    st.session_state.results = []
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp(prefix="anonymizer_")

st.title("Document Metadata Anonymizer")
st.markdown("Inspect hidden data, preview sanitization changes side-by-side, and download cleaned files in batches.")
st.divider()

st.subheader("📁 Step 1: Upload Files")
uploaded_files = st.file_uploader(
    "Drag and drop documents or images here",
    type=["pdf", "docx", "xlsx", "jpg", "jpeg", "png", "tiff", "tif", "bmp"],
    accept_multiple_files=True,
    key="uploader",
)

if uploaded_files:
    st.divider()
    st.subheader("🔍 Step 2: Inspection Queue & Before/After Comparison")

    queue_col, compare_panel = st.columns([1, 2.2], gap="large")

    with queue_col:
        st.write("**Batch Queue:**")
        file_list = [f.name for f in uploaded_files]
        selected_name = st.radio(
            f"Select file ({len(file_list)} loaded):",
            file_list,
            label_visibility="collapsed",
        )
        active_file = next(f for f in uploaded_files if f.name == selected_name)

    # Read real metadata for the selected file
    real_before = {}
    real_after = {}
    try:
        tmp_write = tempfile.mktemp(suffix=os.path.splitext(selected_name)[1])
        tmp_read = tempfile.mktemp(suffix=os.path.splitext(selected_name)[1])
        with open(tmp_read, "wb") as f:
            f.write(active_file.getbuffer())
        real_before = read_metadata(tmp_read)
        from core.orchestrator import strip_metadata as sm
        removed = sm(tmp_read, tmp_write)
        real_after = read_metadata(tmp_write)
        os.unlink(tmp_write)
        os.unlink(tmp_read)
    except Exception:
        real_before = {}
        real_after = {}

    with compare_panel:
        st.markdown(f"##### Live Sanitization Preview: `{selected_name}`")

        before_col, after_col = st.columns(2)
        with before_col:
            before_html = '<div class="compare-card"><h6 style="color:#EF4444;font-weight:bold;margin-bottom:12px;">🔴 ORIGINAL METADATA</h6>'
            if real_before:
                for key, val in real_before.items():
                    if isinstance(val, list):
                        val = ", ".join(str(v) for v in val) if val else "—"
                    elif val is None or str(val) == "None":
                        val = "—"
                    elif not str(val).strip():
                        val = "—"
                    tag = "danger-tag" if str(val) != "—" else ""
                    before_html += f'<p class="muted-text">{key}: <span class="{tag}">{val}</span></p>'
            else:
                before_html += '<p class="muted-text">No metadata found</p>'
            before_html += "</div>"
            st.markdown(before_html, unsafe_allow_html=True)

        with after_col:
            after_html = '<div class="compare-card"><h6 style="color:#10B981;font-weight:bold;margin-bottom:12px;">🟢 CLEANED</h6>'
            if real_after:
                for key, val in real_after.items():
                    if isinstance(val, list):
                        val = ", ".join(str(v) for v in val) if val else "—"
                    elif val is None or str(val) == "None":
                        val = "—"
                    elif not str(val).strip():
                        val = "—"
                    tag = "success-tag" if str(val) == "—" else ""
                    after_html += f'<p class="muted-text">{key}: <span class="{tag}">{val}</span></p>'
            else:
                after_html += '<p class="muted-text">Fields cleared</p>'
            after_html += "</div>"
            st.markdown(after_html, unsafe_allow_html=True)

    st.divider()
    st.subheader("🚀 Step 3: Run Purge Engine")

    if st.button("Purge Hidden Metadata Fields", type="primary", use_container_width=True):
        temp_input = tempfile.mkdtemp(prefix="anonymizer_input_")
        output_dir = tempfile.mkdtemp(prefix="anonymizer_output_")

        file_paths = []
        for uf in uploaded_files:
            p = os.path.join(temp_input, uf.name)
            with open(p, "wb") as f:
                f.write(uf.getbuffer())
            file_paths.append(p)

        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []

        for i, fp in enumerate(file_paths, 1):
            status_text.text(f"Scrubbing: {os.path.basename(fp)}...")
            r = process_single(fp, output_dir)
            results.append(r)
            progress_bar.progress(int(i / len(file_paths) * 100))

        status_text.empty()
        progress_bar.empty()

        success_count = sum(1 for r in results if r["success"])
        fail_count = sum(1 for r in results if not r["success"])
        st.success(f"Purge Complete! {success_count} file(s) cleaned successfully, {fail_count} failed.")
        st.session_state.processed = True
        st.session_state.results = results

        shutil.rmtree(temp_input, ignore_errors=True)

    if st.session_state.processed:
        st.divider()
        st.subheader("📥 Step 4: Export Clean Files")

        success_results = [r for r in st.session_state.results if r["success"]]
        fail_results = [r for r in st.session_state.results if not r["success"]]

        if fail_results:
            for r in fail_results:
                st.markdown(
                    f'<div style="background:#FEF2F2;padding:0.75rem 1rem;border-radius:8px;margin-bottom:0.5rem;font-size:0.85rem;">'
                    f'⚠️ <b>{r["file"]}</b>: {r.get("error", "Unknown error")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        if success_results:
            down_col1, down_col2 = st.columns(2, gap="medium")

            with down_col1:
                st.info("📦 **Batch Action:** Package all cleaned files together")
                zip_path = os.path.join(st.session_state.temp_dir, "sanitized_documents_package.zip")
                create_batch_zip(os.path.dirname(success_results[0]["output_path"]), zip_path)
                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="⚡ Download All Files as ZIP Bundle",
                        data=f,
                        file_name="sanitized_documents_package.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )

            with down_col2:
                st.warning("📄 **Granular Export:** Download files individually")
                for r in st.session_state.results:
                    if r["success"]:
                        base, ext = os.path.splitext(r["file"])
                        final_name = r["file"] if overwrite else f"{base}{suffix}{ext}"
                        with open(r["output_path"], "rb") as f:
                            st.download_button(
                                label=f"Download {final_name}",
                                data=f,
                                file_name=final_name,
                                key=f"dl_{final_name}",
                            )
            st.divider()
            if st.button("Clear & Start Over"):
                st.session_state.processed = False
                st.session_state.results = []
                shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
                st.session_state.temp_dir = tempfile.mkdtemp(prefix="anonymizer_")
                st.rerun()
else:
    st.divider()
    st.info("💡 Upload one or more files above to begin viewing and purging metadata.")
