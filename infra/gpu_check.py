import modal
from infra.costs import track_cost


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.7.1+cu128", index_url="https://download.pytorch.org/whl/cu128")
    .add_local_python_source("infra")
)

app = modal.App("enrich-bench-gpu-check", image=image)

@app.function(gpu="T4", timeout=300, retries=0, cpu=1)
def check_gpu():
    import torch
    import subprocess
    print(torch.__version__)
    print(torch.cuda.get_device_name(0))
    print(torch.cuda.get_device_properties(0).total_memory)
    result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=True)
    print(result.stdout)

@app.local_entrypoint()
def main():
    with track_cost("check_gpu", gpu="T4", cpu_cores=1, n_inputs=1, produces_results=False):
        check_gpu.remote()
