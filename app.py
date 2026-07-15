from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

from core.document_encryptor import is_encrypted as _is_encrypted
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
    st.markdown("### 🛡️ Purge Controls")
    st.caption("Toggle which metadata categories to strip.")

    st.markdown("**Strip Category:**")
    strip_author = st.checkbox("Author / Creator / People", value=True)
    strip_dates = st.checkbox("Timestamps (Creation/Modification)", value=True)
    strip_geo = st.checkbox("GPS & Location Data", value=True)
    strip_software = st.checkbox("Software & Device Footprints", value=True)

    st.divider()
    st.markdown("**Output Preferences:**")
    suffix = st.text_input("Clean File Suffix", value="_anonymized")
    overwrite = st.toggle("Overwrite original names in ZIP", value=False)

    st.divider()
    st.markdown("### 📝 Content Redaction")
    st.caption("Find & redact sensitive text inside document body.")

    redact_email = st.checkbox("Email addresses", value=True)
    redact_phone = st.checkbox("Phone numbers", value=True)
    redact_nin = st.checkbox("National IDs / NIN numbers", value=True)
    redact_credit_card = st.checkbox("Credit card numbers", value=True)
    redact_ip = st.checkbox("IP addresses", value=True)
    redact_api_key = st.checkbox("API keys & tokens", value=False)
    redact_jwt = st.checkbox("JWT tokens", value=False)
    redact_confidential = st.checkbox("Confidential context (keyword-based)", value=False)
    redact_ref_code = st.checkbox("Reference codes (e.g. MOICT/BUD/2026/014)", value=True)
    redact_currency = st.checkbox("Currency amounts (UGX, USD, etc.)", value=True)
    redact_high_entropy = st.checkbox("High-entropy strings (passwords/secrets)", value=False)
    redact_custom_keywords = st.text_input(
        "Extra confidential keywords (comma-separated)",
        value="",
        placeholder="e.g. budget, project-x, codename",
    )

    st.divider()
    st.markdown("### 🔐 Document Encryption")
    encrypt_enabled = st.checkbox("Encrypt document text after anonymization", value=False)
    encrypt_password = st.text_input(
        "Encryption password",
        type="password",
        placeholder="Enter a strong password",
        disabled=not encrypt_enabled,
    )

    st.divider()
    st.caption("🔒 Everything runs locally. No files ever leave your machine.")

strip_filters = {
    "author": strip_author,
    "dates": strip_dates,
    "geo": strip_geo,
    "software": strip_software,
    "redact_email": redact_email,
    "redact_phone": redact_phone,
    "redact_nin": redact_nin,
    "redact_credit_card": redact_credit_card,
    "redact_ip": redact_ip,
    "redact_api_key": redact_api_key,
    "redact_jwt": redact_jwt,
    "redact_confidential": redact_confidential,
    "redact_ref_code": redact_ref_code,
    "redact_currency": redact_currency,
    "redact_high_entropy": redact_high_entropy,
    "redact_custom_keywords": redact_custom_keywords,
    "encrypt_enabled": encrypt_enabled,
    "encrypt_password": encrypt_password if encrypt_enabled else "",
}


st.markdown("""
<style>
    :root {
        --bg: #F8FAFC;
        --card: #FFFFFF;
        --text: #0F172A;
        --text-muted: #64748B;
        --border: #E2E8F0;
        --accent: #0D9488;
        --accent-hover: #14B8A6;
        --red: #EF4444;
        --green: #10B981;
        --red-bg: #FEF2F2;
        --green-bg: #F0FDF4;
        --amber-bg: #FFFBEB;
        --blue-bg: #EFF6FF;
        --radius: 12px;
    }

    .stApp {
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--card) !important;
        border-right: 1px solid var(--border) !important;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {
        color: var(--text) !important;
    }
    section[data-testid="stSidebar"] hr {
        border-color: var(--border) !important;
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--text) !important;
        font-weight: 600 !important;
    }
    p, span, label, .stMarkdown p {
        color: var(--text) !important;
    }

    div[data-testid="stFileUploader"] section {
        border: 2px dashed #CBD5E1 !important;
        border-radius: var(--radius) !important;
        background: var(--card) !important;
        padding: 2.5rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stFileUploader"] section:hover {
        border-color: var(--accent) !important;
        background: #F0FDFA !important;
    }
    div[data-testid="stFileUploader"] small {
        color: var(--text-muted) !important;
    }

    .stButton > button {
        font-weight: 500 !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.15s ease !important;
        border: 1px solid var(--border) !important;
        background: var(--card) !important;
        color: var(--text) !important;
    }
    .stButton > button[kind="primary"] {
        background: var(--accent) !important;
        border-color: var(--accent) !important;
        color: white !important;
        font-weight: 600 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--accent-hover) !important;
        border-color: var(--accent-hover) !important;
        box-shadow: 0 2px 8px rgba(13,148,136,0.3) !important;
    }
    div.st-bv {
        background-color: var(--accent) !important;
    }

    div[data-testid="stRadio"] label {
        color: var(--text) !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        padding: 0.5rem !important;
    }
    div[data-testid="stRadio"] input[type="radio"]:checked + div {
        background-color: var(--accent) !important;
        color: white !important;
        border-radius: 6px !important;
    }

    div[data-testid="stCheckbox"] label {
        color: var(--text) !important;
    }
    div[data-testid="stCheckbox"] input:checked ~ div {
        background-color: var(--accent) !important;
        border-color: var(--accent) !important;
    }

    div[data-testid="stTextInput"] input {
        background: var(--card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
    }

    div[data-testid="stToggle"] {
        background: var(--border) !important;
    }
    div[data-testid="stToggle"][aria-checked="true"] {
        background: var(--accent) !important;
    }

    .stProgress > div > div > div {
        background-color: var(--accent) !important;
    }
    .stProgress > div {
        background-color: var(--border) !important;
        border-radius: 4px !important;
    }

    .stAlert {
        border-radius: 8px !important;
        border: none !important;
    }
    .stAlert.st-info {
        background: var(--blue-bg) !important;
        color: #1E40AF !important;
    }
    .stAlert.st-warning {
        background: var(--amber-bg) !important;
        color: #92400E !important;
    }
    .stAlert.st-success {
        background: var(--green-bg) !important;
        color: #065F46 !important;
    }
    .stAlert.st-error {
        background: var(--red-bg) !important;
        color: #991B1B !important;
    }
    .stAlert p {
        color: inherit !important;
    }

    div[data-testid="stDownloadButton"] button {
        background: var(--accent) !important;
        color: white !important;
        border: none !important;
        font-weight: 500 !important;
    }
    div[data-testid="stDownloadButton"] button:hover {
        background: var(--accent-hover) !important;
        box-shadow: 0 2px 8px rgba(13,148,136,0.3) !important;
    }

    header[data-testid="stHeader"] {
        background-color: var(--card) !important;
        border-bottom: 1px solid var(--border) !important;
    }
    header[data-testid="stHeader"] * { color: var(--text) !important; }


    .step-nav {
        display: flex; align-items: center; justify-content: center;
        gap: 0; margin: 1.5rem 0 2rem 0;
    }
    .step-item {
        display: flex; align-items: center; gap: 0.5rem;
    }
    .step-circle {
        width: 32px; height: 32px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.8rem; font-weight: 700;
        border: 2px solid var(--border);
        color: var(--text-muted); background: var(--card);
        transition: all 0.2s ease;
    }
    .step-circle.active {
        border-color: var(--accent); background: var(--accent);
        color: white; box-shadow: 0 2px 8px rgba(13,148,136,0.3);
    }
    .step-circle.done {
        border-color: var(--green); background: var(--green-bg);
        color: var(--green);
    }
    .step-label {
        font-size: 0.8rem; font-weight: 500;
        color: var(--text-muted); white-space: nowrap;
    }
    .step-label.active { color: var(--accent); font-weight: 700; }
    .step-label.done { color: var(--green); }
    .step-connector {
        width: 48px; height: 2px; background: var(--border);
        margin: 0 0.75rem; flex-shrink: 0;
    }
    .step-connector.done { background: var(--green); }

    .st-emotion-cache-1mi2ry2,
    .st-emotion-cache-1r4qj8v,
    .st-emotion-cache-6qob1r {
        background-color: var(--card) !important;
    }

    hr {
        border-color: var(--border) !important;
        margin: 1.5rem 0 !important;
    }

    .compare-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem;
        min-height: 250px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .danger-tag {
        color: var(--red); font-weight: 600;
        background: rgba(239,68,68,0.1); padding: 2px 8px; border-radius: 4px;
    }
    .success-tag {
        color: var(--green); font-weight: 600;
        background: rgba(16,185,129,0.1); padding: 2px 8px; border-radius: 4px;
    }
    .muted-text {
        color: var(--text-muted) !important; font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

if "processed" not in st.session_state:
    st.session_state.processed = False
    st.session_state.results = []
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp(prefix="anonymizer_")

st.title("Document Metadata Anonymizer")
st.markdown("Inspect hidden data, preview sanitization changes side-by-side, and download cleaned files in batches.")

uploaded = st.session_state.get("uploader", None)
step = 1
if st.session_state.get("uploader"):
    step = 2
if st.session_state.processed:
    step = 4
elif st.session_state.get("purge_clicked"):
    step = 3

steps = ["Upload", "Inspect", "Purge", "Export"]
step_icons = ["📁", "🔍", "🚀", "📥"]

nav_html = '<div class="step-nav">'
for i, (s, icon) in enumerate(zip(steps, step_icons), 1):
    cls = "active" if i == step else ("done" if i < step else "")
    nav_html += f"""
        <div class="step-item">
            <div class="step-circle {cls}">{icon}</div>
            <span class="step-label {cls}">Step {i}: {s}</span>
        </div>"""
    if i < len(steps):
        nav_html += f'<div class="step-connector {"done" if i < step else ""}"></div>'
nav_html += "</div>"
st.markdown(nav_html, unsafe_allow_html=True)
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

        notices = []
        if any(k.startswith("redact_") and v for k, v in strip_filters.items() if k not in ("redact_custom_keywords", "encrypt_enabled", "encrypt_password")):
            notices.append("📝 Content redaction active — sensitive patterns replaced with <code>[REDACTED]</code>")
        if encrypt_enabled and encrypt_password:
            notices.append("🔐 Document encryption active — body text will be AES-encrypted after processing")
        if notices:
            st.markdown(
                f'<div style="background:#FFFBEB;padding:0.75rem 1rem;border-radius:8px;margin-top:12px;'
                f'font-size:0.85rem;border:1px solid #FDE68A;">'
                + "<br>".join(notices) +
                '</div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.subheader("🚀 Step 3: Sanitize & Export")

    if st.button("⚡ Purge All Metadata & Sensitive Content", type="primary", use_container_width=True):
        st.session_state.purge_clicked = True
        temp_input = tempfile.mkdtemp(prefix="anonymizer_input_")
        output_dir = tempfile.mkdtemp(prefix="anonymizer_output_")

        file_paths = []
        for uf in uploaded_files:
            p = os.path.join(temp_input, uf.name)
            with open(p, "wb") as f:
                f.write(uf.getbuffer())
            file_paths.append(p)

        with st.spinner("Processing..."):
            results = []
            for fp in file_paths:
                r = process_single(fp, output_dir, filters=strip_filters)
                results.append(r)

        st.session_state.processed = True
        st.session_state.results = results
        shutil.rmtree(temp_input, ignore_errors=True)

    if st.session_state.processed:
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
            st.divider()
            st.subheader("📥 Download Clean Files")
            st.caption("Metadata stripped and sensitive content redacted. Files are yours — nothing stored remotely.")
            if encrypt_enabled and encrypt_password:
                st.info(
                    "🔐 Files are AES-encrypted with your password. To decrypt, use the Python script below "
                    "or run: `python3 -c \"from core.document_encryptor import decrypt_document; "
                    "decrypt_document('encrypted.docx', 'decrypted.docx', 'YOUR_PASSWORD')\"`"
                )

            redacted_files = [r for r in success_results if r.get("redaction")]
            if redacted_files:
                for r in redacted_files:
                    rc = r["redaction"]
                    if rc.get("total", 0) > 0:
                        details = ", ".join(
                            f"{k}: {v}" for k, v in sorted(rc.items()) if k != "total" and v > 0
                        )
                        st.markdown(
                            f'<div style="background:#FFFBEB;padding:0.5rem 1rem;border-radius:8px;'
                            f'margin-bottom:0.3rem;font-size:0.85rem;border:1px solid #FDE68A;">'
                            f'📝 <b>{r["file"]}</b>: {rc["total"]} item(s) redacted ({details})'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

            zip_path = os.path.join(st.session_state.temp_dir, "sanitized_documents_package.zip")
            create_batch_zip(os.path.dirname(success_results[0]["output_path"]), zip_path)
            any_enc = any(
                _is_encrypted(r["output_path"])
                for r in success_results
            )
            with open(zip_path, "rb") as f:
                st.download_button(
                    label="🔐 Download All as ZIP (encrypted)" if any_enc else "📦 Download All as ZIP",
                    data=f,
                    file_name="sanitized_documents_package.zip",
                    mime="application/zip",
                    use_container_width=True,
                )

            for r in success_results:
                is_enc = _is_encrypted(r["output_path"])
                base, ext = os.path.splitext(r["file"])
                tag = "_encrypted" if is_enc else ""
                final_name = r["file"] if overwrite else f"{base}{suffix}{tag}{ext}"
                icon = "🔐 " if is_enc else "⬇ "
                with open(r["output_path"], "rb") as f:
                    st.download_button(
                        label=f"{icon}{final_name}",
                        data=f,
                        file_name=final_name,
                        key=f"dl_{final_name}",
                        use_container_width=True,
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
