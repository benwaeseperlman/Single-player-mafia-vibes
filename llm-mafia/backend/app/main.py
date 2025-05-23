from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers and services
from app.api import game_endpoints
from app.api import websocket_endpoints

app = FastAPI(
    title="LLM Mafia Game",
    description="Single-player Mafia game with LLM-powered AI players",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be restricted to the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint to verify the API is running."""
    return {"status": "healthy", "version": app.version}

# Include routers here as they are developed
# from app.api import game_endpoints
# app.include_router(game_endpoints.router, prefix="/api")
app.include_router(game_endpoints.router, prefix="/api", tags=["Game Management"])
app.include_router(websocket_endpoints.router, tags=["WebSocket"])

# TODO: Add WebSocket endpoint router

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 