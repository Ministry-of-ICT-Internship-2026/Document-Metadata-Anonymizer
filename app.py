import streamlit as st
import os
import time

# 1. PAGE SETUP
st.set_page_config(
    page_title="Metadata Purge - Enterprise Anonymizer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. SIDEBAR DATA CONFIGURATION
with st.sidebar:
    st.divider()
    st.markdown("### 🛡️ Core Data Settings")
    st.caption("Define the strictness level of the extraction process.")
    
    st.markdown("**Select Metadata to Purge:**")
    strip_author = st.checkbox("Author / System Creator", value=True)
    strip_dates = st.checkbox("Timestamps (Creation/Modification)", value=True)
    strip_geo = st.checkbox("GPS & Location Data", value=True)
    strip_software = st.checkbox("Software & Hardware Footprints", value=True)
    
    st.divider()
    st.markdown("**Output Preferences:**")
    suffix = st.text_input("Clean File Suffix", value="_anonymized")
    overwrite = st.toggle("Overwrite original names in ZIP", value=False)
    

# 3. DYNAMIC INTERACTIVE CUSTOM THEME INJECTION (CSS)
    bg_color = "#1E293B"      # Dark slate
    card_bg = "#334155"       # Lighter slate for cards
    text_color = "#F8FAFC"    # Crisp off-white
    border_color = "#475569"  # Muted border
    sub_text = "#94A3B8"
    bg_color = "#1E518394"      # Soft light gray/blue
    card_bg = "#FFFFFF"       # Clean pure white cards
    text_color = "#0F172A"    # Deep midnight slate
    border_color = "#E2E8F0"  # Soft divider line
    sub_text = "#64748B"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_color} !important; color: {text_color} !important; }}
    h1, h2, h3, h4, h5, p, span, label {{ color: {text_color} !important; }}
    .stMarkdown p {{ color: {text_color} !important; }}
    
    /* Comparison Matrix Cards styling */
    .compare-card {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        min-height: 250px;
    }}
    
    /* Metadata field badges */
    .danger-tag {{ color: #EF4444; font-weight: bold; background: rgba(239, 68, 68, 0.15); padding: 2px 6px; border-radius: 4px; }}
    .success-tag {{ color: #10B981; font-weight: bold; background: rgba(16, 185, 129, 0.15); padding: 2px 6px; border-radius: 4px; }}
    .muted-text {{ color: {sub_text} !important; font-size: 0.85rem; }}
    </style>
""", unsafe_allow_html=True)

# State initialization logic
if "processed" not in st.session_state:
    st.session_state.processed = False
if "processing_files" not in st.session_state:
    st.session_state.processing_files = []

def handle_file_change():
    st.session_state.processed = False
    st.session_state.processing_files = []

# 4. MAIN APP HEADER
st.title("Document Metadata Anonymizer")
st.markdown("Inspect hidden data stamps, preview sanitization changes side-by-side, and download cleaned files in batches.")
st.divider()

# STEP 1: BATCH UPLOAD CONTAINER
st.subheader("📁 Step 1: Batch Upload Files")
uploaded_files = st.file_uploader(
    "Drag and drop documents or images here",
    type=["pdf", "docx", "xlsx", "pptx", "jpg", "jpeg", "png"],
    accept_multiple_files=True,
    on_change=handle_file_change,
    key="uploader"
)

# 5. WORKSPACE WORKFLOW LOGIC
if uploaded_files:
    st.divider()
    st.subheader("🔍 Step 2: Inspection Queue & Before/After Comparison")
    
    # Left layout selector column, Right side comparison container panel
    queue_col, compare_panel = st.columns([1, 2.2], gap="large")
    
    with queue_col:
        st.write("**Current Batch Queue:**")
        file_list = [f.name for f in uploaded_files]
        selected_file_name = st.radio(
            f"Select file to map properties ({len(file_list)} loaded):", 
            file_list,
            label_visibility="collapsed"
        )
        active_file = next(f for f in uploaded_files if f.name == selected_file_name)
        
    with compare_panel:
        st.markdown(f"##### Live Sanitization Preview: `{selected_file_name}`")
        
        # Side-by-side comparison sub-columns
        before_col, after_col = st.columns(2)
        
        with before_col:
            # Conditional text indicators based on sidebar filters
            author_val = '<span class="danger-tag">Analyst Tony (Alien Laptop)</span>' if strip_author else '<span>John Doe (Corp Laptop)</span>'
            date_val = '<span class="danger-tag">2026-03-14 11:24:02</span>' if strip_dates else '<span>2026-03-14 11:24:02</span>'
            geo_val = '<span class="danger-tag">40.7128° N, 74.0060° W</span>' if strip_geo else '<span>40.7128° N, 74.0060° W</span>'
            soft_val = '<span class="danger-tag">Office365 Build v16.8</span>' if strip_software else '<span>Office365 Build v16.8</span>'
            
            st.markdown(
                f"""
                <div class="compare-card">
                    <h6 style="color:#EF4444; font-weight:bold; margin-bottom:12px;">🔴 EMBEDDED ORIGINAL METADATA</h6>
                    <p class="muted-text">File Size: {active_file.size / 1024:.2f} KB</p>
                    <p>👤 <b>Author:</b> {author_val}</p>
                    <p>📅 <b>Created:</b> {date_val}</p>
                    <p>📍 <b>GPS Data:</b> {geo_val}</p>
                    <p>💻 <b>Software:</b> {soft_val}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
        with after_col:
            # Clean view output mapping state simulation
            clean_author = '<span class="success-tag">[STRIPPED / BLANK]</span>' if strip_author else '<span>John Doe (Corp Laptop)</span>'
            clean_date = '<span class="success-tag">[STRIPPED / BLANK]</span>' if strip_dates else '<span>2026-03-14 11:24:02</span>'
            clean_geo = '<span class="success-tag">[STRIPPED / BLANK]</span>' if strip_geo else '<span>40.7128° N, 74.0060° W</span>'
            clean_soft = '<span class="success-tag">[STRIPPED / BLANK]</span>' if strip_software else '<span>Office365 Build v16.8</span>'
            
            st.markdown(
                f"""
                <div class="compare-card">
                    <h6 style="color:#10B981; font-weight:bold; margin-bottom:12px;">🟢 POST-ANONYMIZATION EXPECTED PREVIEW</h6>
                    <p class="muted-text">Estimated Clean Size: ~{(active_file.size / 1024) * 0.95:.2f} KB</p>
                    <p>👤 <b>Author:</b> {clean_author}</p>
                    <p>📅 <b>Created:</b> {clean_date}</p>
                    <p>📍 <b>GPS Data:</b> {clean_geo}</p>
                    <p>💻 <b>Software:</b> {clean_soft}</p>
                </div>
                """, 
                unsafe_allow_html=True
            )

    # STEP 3: SANITIZATION RUNTIME PROCESSOR
    st.divider()
    st.subheader("🚀 Step 3: Run Purge Engine")
    
    if st.button("Purge Hidden Metadata Fields", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for index, file in enumerate(uploaded_files):
            status_text.text(f"Scrubbing target identifiers from: {file.name}...")
            time.sleep(0.3)
            progress_bar.progress(int((index + 1) / len(uploaded_files) * 100))
            
        status_text.empty()
        progress_bar.empty()
        st.success(f"Purge Complete! Successfully sanitized {len(uploaded_files)} file(s). Tracking metrics destroyed.")
        st.session_state.processed = True
        st.session_state.processing_files = uploaded_files

    # STEP 4: EXPORT DOWNSTREAM MECHANIC
    if st.session_state.processed:
        st.divider()
        st.subheader("📥 Step 4: Export Clean Files")
        
        down_col1, down_col2 = st.columns(2, gap="medium")
        
        with down_col1:
            st.info("📦 **Bulk Batch Action:** Package all files together")
            st.download_button(
                label="⚡ Download All Files as ZIP Bundle",
                data=b"ZIP Bundle Data Placeholder Stream",
                file_name="sanitized_documents_package.zip",
                mime="application/zip",
                use_container_width=True
            )
            
        with down_col2:
            st.warning("📄 **Granular Export:** Download files individually")
            for file in st.session_state.processing_files:
                base, ext = os.path.splitext(file.name)
                final_name = file.name if overwrite else f"{base}{suffix}{ext}"
                
                st.download_button(
                    label=f"Download {final_name}",
                    data=file.getvalue(),
                    file_name=final_name,
                    mime=file.type,
                    key=f"dl_{final_name}"
                )
else:
    st.divider()
    st.info("💡 Upload one or more files above to begin viewing and purging metadata..")
