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

# Create the FastAPI application instance.
# - title: shown in the auto-generated API docs at /docs
# - description: also shown in the API docs
# - version: the current API version
app = FastAPI(
    title="RepoPilot",
    description="AI Software Engineering Intelligence Platform",
    version="0.1.0",
)


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
