from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="Orchids Website Cloner API",
    description="AI-powered website cloning service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Orchids Website Cloner API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "website-cloner-api"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)