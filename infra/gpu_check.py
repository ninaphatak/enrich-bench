import modal
import time


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.7.1+cu128", index_url="https://download.pytorch.org/whl/cu128")
)

app = modal.App("enrich-bench-gpu-check", image=image)

@app.function(gpu="T4", timeout=300, retries=0)
def check_gpu():
    import torch
    import subprocess
    print(torch.__version__)
    print(torch.cuda.get_device_name(0))
    print(torch.cuda.get_device_properties(0).total_memory)
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error executing nvidia-smi:", e)
        print("Output:", e.output)

@app.local_entrypoint()
def main():
    start_time = time.perf_counter()
    check_gpu.remote()
    end_time = time.perf_counter()
    print(f"GPU check completed in {end_time - start_time:.2f} seconds")
