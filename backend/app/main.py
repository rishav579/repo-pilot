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

from fastapi import FastAPI

from app.api.router_parsing import router as parsing_router
from app.api.router_repositories import router as repositories_router

# Create the FastAPI application instance.
# - title: shown in the auto-generated API docs at /docs
# - description: also shown in the API docs
# - version: the current API version
app = FastAPI(
    title="RepoPilot",
    description="AI Software Engineering Intelligence Platform",
    version="0.1.0",
)

# Register API routers.
# Each router handles a group of related endpoints.
# - repositories router adds: POST /repositories/scan
# - parsing router adds:      POST /repositories/parse
app.include_router(repositories_router)
app.include_router(parsing_router)


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
