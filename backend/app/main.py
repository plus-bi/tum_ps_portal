from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import router
from .account_api import router as account_router

app = FastAPI(title="TUM Project Studies Portal", version="1.0.0", docs_url="/api/docs")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost", "http://localhost:3000"], allow_methods=["GET"], allow_headers=["*"])
app.include_router(router)
app.include_router(account_router)


@app.get("/health")
def health(): return {"status": "ok"}


@app.get("/ready")
def ready(): return {"status": "ready"}
