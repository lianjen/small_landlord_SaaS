"""
MicroRent API Gateway (FastAPI)
The brain of the new architecture.
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from datetime import datetime

# Import routers
from routers import tenant, auth, payment, repair

# Initialize FastAPI
app = FastAPI(
    title="MicroRent API",
    description="Backend for Tenant App & Landlord Dashboard",
    version="2.0.0"
)

# CORS (Allow Frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(tenant.router)
app.include_router(payment.router)
app.include_router(repair.router)

@app.get("/")
async def root():
    return {
        "message": "MicroRent API v2.0 is running 🚀",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/health")
async def health_check():
    """System Health Check"""
    return {"status": "healthy", "service": "backend"}
