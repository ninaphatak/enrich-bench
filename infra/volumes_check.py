import modal
from infra.volumes import data
from pathlib import Path

image = modal.Image.debian_slim(python_version="3.11").add_local_python_source("infra")

app = modal.App("enrich-bench-volumes-check", image = image)

@app.function(timeout=60, retries=0, volumes={"/data":data})
def write_file():
    p = Path("/data/scratch/test.txt")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("This is a test file for volume check")
    data.commit()

@app.function(timeout=60, retries=0, volumes={"/data":data})
def read_file():
    p = Path("/data/scratch/test.txt")
    return p.read_text() if p.exists() else None

@app.local_entrypoint()
def main():
    write_file.remote()
    print(read_file.remote())

