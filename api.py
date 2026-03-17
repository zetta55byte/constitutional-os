from fastapi import FastAPI

app = FastAPI(title="Constitutional OS", version="0.1.0")

@app.get("/")
def root():
    return {"service": "Constitutional OS", "status": "running", "version": "0.1.0"}

@app.get("/api/status")
def status():
    return {"status": "running"}