"""
RepoPilot — Backend Application Entry Point

This is the main FastAPI application file.
It creates the FastAPI app instance and defines API endpoints.

How to run:
    cd backend
    uvicorn app.main:app --reload

    --reload: auto-restarts the server when you change code (development only)

What is "app.main:app"?
    - "app.main" = the Python module path (app/main.py)
    - ":app"     = the variable name of the FastAPI instance inside that file
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router_parsing import router as parsing_router
from app.api.router_rag import router as rag_router
from app.api.router_repositories import router as repositories_router
from app.api.router_retrieval import router as retrieval_router

# Create the FastAPI application instance.
app = FastAPI(
    title="RepoPilot",
    description="AI Software Engineering Intelligence Platform",
    version="0.1.0",
)

# Configure CORS dynamically from environment for local development & deployment
cors_origins_env = os.getenv(
    "REPOPILOT_CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,http://localhost:80,http://127.0.0.1:80",
)
origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers.
# Each router handles a group of related endpoints.
# - repositories router adds: POST /repositories/scan
# - parsing router adds:      POST /repositories/parse
# - retrieval router adds:    POST /repositories/search/keyword
# - rag router adds:          POST /repositories/query
app.include_router(repositories_router)
app.include_router(parsing_router)
app.include_router(retrieval_router)
app.include_router(rag_router)


@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns {"status": "ok"} to confirm the API is running.

    This is the simplest possible endpoint — it takes no input
    and returns a fixed response. Every production API has one
    so monitoring tools can check if the service is alive.
    """
    return {"status": "ok"}
