from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
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
