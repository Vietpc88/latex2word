import streamlit as st
import os
import tempfile
from pathlib import Path
from latex_to_word import latex_to_word_converter
from markdown_to_word import markdown_to_word
from latex_bib_to_word import convert_bib_to_word

# Page configuration
st.set_page_config(
    page_title="TeX Math to Word Converter",
    page_icon="📄",
    layout="centered"
)

# Custom Styling
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .stHeader {
        color: #1e3a8a;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧮 TeX Math to Word Converter")
st.markdown("Convert your LaTeX, Markdown, or BibTeX files to Microsoft Word documents with **native math equations**!")

# Sidebar for mode selection
st.sidebar.header("Settings")
mode = st.sidebar.selectbox(
    "Select Conversion Type",
    ("LaTeX (.tex)", "Markdown (.md)", "BibTeX (.bib)")
)

st.sidebar.markdown("---")
st.sidebar.info("""
**How to deploy online:**
1. Push this directory to GitHub.
2. Link to [Streamlit Cloud](https://share.streamlit.io/).
3. Add `packages.txt` with `pandoc`.
""")

# File uploader
file_types = {
    "LaTeX (.tex)": ["tex"],
    "Markdown (.md)": ["md"],
    "BibTeX (.bib)": ["bib"]
}

uploaded_file = st.file_uploader(f"Upload your {mode} file", type=file_types[mode])

if uploaded_file is not None:
    filename = uploaded_file.name
    st.success(f"File '{filename}' uploaded successfully!")
    
    if st.button("Convert to Word"):
        with st.spinner("Processing... This may take a few seconds due to math rendering."):
            # Create a temporary directory to store files
            with tempfile.TemporaryDirectory() as tmpdir:
                # Save uploaded file to temp path
                input_path = os.path.join(tmpdir, filename)
                with open(input_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Perform conversion based on mode
                output_filename = Path(filename).stem + ".docx"
                output_path = os.path.join(tmpdir, output_filename)
                
                # Change CWD to tmpdir for the converter to work properly with output paths
                old_cwd = os.getcwd()
                os.chdir(tmpdir)
                
                try:
                    success = False
                    if mode == "LaTeX (.tex)":
                        # We use the main logic from latex_to_word
                        # Note: In the actual script it's named 'latex_to_word'
                        from latex_to_word import latex_to_word as run_conv
                        result = run_conv(input_path, output_filename, verbose=True)
                        if result: success = True
                    elif mode == "Markdown (.md)":
                        from markdown_to_word import markdown_to_word as run_conv
                        result = run_conv(input_path, output_filename, verbose=True)
                        if result: success = True
                    elif mode == "BibTeX (.bib)":
                        from latex_bib_to_word import convert_bib_to_word as run_conv
                        run_conv(input_path) # This script writes to Path.cwd() / stem.docx
                        if os.path.exists(output_filename): success = True
                    
                    if success:
                        st.balloons()
                        st.success("✅ Conversion Complete!")
                        
                        # Read the file for download
                        with open(output_filename, "rb") as f:
                            btn = st.download_button(
                                label="📥 Download Word Document",
                                data=f,
                                file_name=output_filename,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                    else:
                        st.error("❌ Conversion failed. Please check your file content.")
                
                except Exception as e:
                    st.error(f"Error during processing: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                
                finally:
                    os.chdir(old_cwd)

st.markdown("---")
st.caption("Powered by Pandoc & Python-Docx")
