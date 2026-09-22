import modal
import socket

app = modal.App("enrich-bench-hello")

@app.function()
def add (a: int, b:int) -> int:
    print("add running on:", socket.gethostname())
    return a + b

@app.local_entrypoint()
def main():
    print("main running on:", socket.gethostname()) 
    print(add.remote(2,3))