from fastapi import FastAPI
from sqlalchemy import text

from app.auth.router import router as auth_router
from app.workspaces.router import router as workspace_router
from app.documents.router import router as document_router

from app.db.database import engine

app = FastAPI(title="IntelliVault API")

app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(document_router)

@app.get("/health")
async def health():
    return {"status" : "ok"}

