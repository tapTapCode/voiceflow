"""
VoiceFlow API - Main FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from backend.database import init_db
from backend.inbound.routes import router as inbound_router
from backend.outbound.routes import router as outbound_router

# Create FastAPI app
app = FastAPI(
    title="VoiceFlow API",
    description="AI-powered voice agents for customer support and lead generation",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(inbound_router)
app.include_router(outbound_router)


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "VoiceFlow API",
        "version": "0.1.0",
        "docs": "/docs",
        "agents": [
            {
                "name": "inbound",
                "description": "Customer support agent",
                "endpoints": "/api/inbound",
            }
        ],
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "development") == "development",
    )
