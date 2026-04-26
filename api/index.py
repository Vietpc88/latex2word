from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
import os
import shutil
import tempfile
import subprocess
from pathlib import Path
import sys

# Add parent directory to path so we can import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from latex_to_word import latex_to_word as conv_latex
from markdown_to_word import markdown_to_word as conv_md
from latex_bib_to_word import convert_bib_to_word as conv_bib

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TeX to Word Converter</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
        }
        body {
            font-family: 'Inter', sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            width: 100%;
            max-width: 500px;
            padding: 2rem;
            background: var(--card);
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1);
            border-radius: 1rem;
            text-align: center;
        }
        h1 { font-weight: 600; margin-bottom: 0.5rem; color: var(--primary); }
        p { color: #64748b; margin-bottom: 2rem; }
        .upload-area {
            border: 2px dashed #cbd5e1;
            padding: 2rem;
            border-radius: 0.75rem;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 1.5rem;
        }
        .upload-area:hover { border-color: var(--primary); background: #eff6ff; }
        select {
            width: 100%;
            padding: 0.75rem;
            border-radius: 0.5rem;
            border: 1px solid #cbd5e1;
            margin-bottom: 1.5rem;
            font-size: 1rem;
        }
        button {
            width: 100%;
            padding: 0.75rem;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover { background: var(--primary-hover); }
        button:disabled { background: #94a3b8; cursor: not-allowed; }
        #status { margin-top: 1rem; font-size: 0.875rem; }
        .loading { display: none; margin: 10px auto; border: 3px solid #f3f3f3; border-top: 3px solid var(--primary); border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>TeX Math to Word</h1>
        <p>Convert LaTeX, Markdown or BibTeX online</p>
        
        <form id="convertForm">
            <div class="upload-area" id="dropZone">
                <input type="file" id="fileInput" hidden required>
                <span id="fileName">Drop file here or click to upload</span>
            </div>
            
            <select id="modeSelect">
                <option value="latex">LaTeX (.tex)</option>
                <option value="markdown">Markdown (.md)</option>
                <option value="bibtex">BibTeX (.bib)</option>
            </select>
            
            <button type="submit" id="submitBtn">Convert Now</button>
        </form>
        
        <div class="loading" id="loader"></div>
        <div id="status"></div>
    </div>

    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const fileName = document.getElementById('fileName');
        const form = document.getElementById('convertForm');
        const status = document.getElementById('status');
        const loader = document.getElementById('loader');
        const submitBtn = document.getElementById('submitBtn');

        dropZone.onclick = () => fileInput.click();
        
        fileInput.onchange = () => {
            if (fileInput.files.length > 0) {
                fileName.textContent = fileInput.files[0].name;
                // Auto select mode based on extension
                const ext = fileInput.files[0].name.split('.').pop().toLowerCase();
                if (ext === 'tex') document.getElementById('modeSelect').value = 'latex';
                if (ext === 'md') document.getElementById('modeSelect').value = 'markdown';
                if (ext === 'bib') document.getElementById('modeSelect').value = 'bibtex';
            }
        };

        form.onsubmit = async (e) => {
            e.preventDefault();
            const file = fileInput.files[0];
            const mode = document.getElementById('modeSelect').value;
            
            if (!file) return;

            status.textContent = 'Processing... This might take 30s as Pandoc is being set up.';
            loader.style.display = 'block';
            submitBtn.disabled = true;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('mode', mode);

            try {
                const response = await fetch('/api/convert', {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = file.name.split('.')[0] + '.docx';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    status.textContent = '✅ Success! Your download should start shortly.';
                } else {
                    const err = await response.json();
                    status.textContent = '❌ Error: ' + (err.detail || 'Conversion failed');
                }
            } catch (e) {
                status.textContent = '❌ Error: Could not connect to server';
            } finally {
                loader.style.display = 'none';
                submitBtn.disabled = false;
            }
        };
    </script>
</body>
</html>
"""

app = FastAPI()

PANDOC_PATH = "/tmp/pandoc"

def ensure_pandoc():
    """Ensure pandoc is available in the Vercel environment."""
    if shutil.which("pandoc"):
        return "pandoc"
    
    if os.path.exists(PANDOC_PATH):
        return PANDOC_PATH
    
    # Download static pandoc binary for Linux
    print("Downloading pandoc static binary...")
    url = "https://github.com/jgm/pandoc/releases/download/3.1.1/pandoc-3.1.1-linux-amd64.tar.gz"
    tar_path = "/tmp/pandoc.tar.gz"
    
    try:
        import urllib.request
        urllib.request.urlretrieve(url, tar_path)
        
        # Extract
        import tarfile
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path="/tmp")
        
        # Move binary - check for both possible folder names
        possible_bins = [
            "/tmp/pandoc-3.1.1/bin/pandoc",
            "/tmp/pandoc-3.1.1-linux-amd64/bin/pandoc"
        ]
        for extracted_bin in possible_bins:
            if os.path.exists(extracted_bin):
                shutil.move(extracted_bin, PANDOC_PATH)
                os.chmod(PANDOC_PATH, 0o755)
                return PANDOC_PATH
    except Exception as e:
        print(f"Failed to download pandoc: {e}")
    
    return None

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_CONTENT

@app.get("/api/health")
@app.get("/health")
def health():
    # Proactively ensure pandoc is here when they check health
    pandoc_exe = ensure_pandoc()
    return {"status": "ok", "pandoc": bool(shutil.which("pandoc") or os.path.exists(PANDOC_PATH))}

@app.post("/api/convert")
@app.post("/convert")
async def convert(
    file: UploadFile = File(...),
    mode: str = Form(...)
):
    # Ensure pandoc is ready
    pandoc_exe = ensure_pandoc()
    if not pandoc_exe:
        raise HTTPException(status_code=500, detail="Pandoc binary could not be initialized")
    
    # Add to PATH so the scripts can find it
    os.environ["PATH"] = f"/tmp:{os.environ.get('PATH', '')}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, file.filename)
        output_filename = Path(file.filename).stem + ".docx"
        output_path = os.path.join(tmpdir, output_filename)
        
        # Save upload
        with open(input_path, "wb") as f:
            f.write(await file.read())
        
        # Switch CWD
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            success = False
            if mode == "latex":
                result = conv_latex(input_path, output_filename)
                if result: success = True
            elif mode == "markdown":
                result = conv_md(input_path, output_filename)
                if result: success = True
            elif mode == "bibtex":
                conv_bib(input_path)
                if os.path.exists(output_filename): success = True
            
            if success:
                # Move to a persistent temp location to serve
                final_output = os.path.join("/tmp", output_filename)
                shutil.copy(output_path, final_output)
                return FileResponse(
                    final_output, 
                    filename=output_filename,
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                raise HTTPException(status_code=400, detail="Conversion failed")
        
        finally:
            os.chdir(old_cwd)

# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
