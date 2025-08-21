"""
Enhanced WhisperLive Server with production-ready features
Includes authentication, monitoring, rate limiting, and improved architecture
"""

import os
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
import ssl
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
from pydantic import BaseModel

from whisper_live.auth import auth_manager, require_auth, Token, User
from whisper_live.monitoring import metrics, health, logger, log_performance, trace_span
from whisper_live.server import ClientManager
from whisper_live.backend.base import ServeClientBase

# Configuration
HOST = os.getenv("SERVER_HOST", "0.0.0.0")
PORT = int(os.getenv("SERVER_PORT", "9090"))
MAX_CLIENTS = int(os.getenv("MAX_CLIENTS", "10"))
MAX_CONNECTION_TIME = int(os.getenv("MAX_CONNECTION_TIME", "3600"))
ENABLE_SSL = os.getenv("ENABLE_SSL", "false").lower() == "true"
SSL_CERT = os.getenv("SSL_CERT_FILE")
SSL_KEY = os.getenv("SSL_KEY_FILE")

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = os.getenv("CORS_ALLOW_METHODS", "GET,POST").split(",")
CORS_ALLOW_HEADERS = os.getenv("CORS_ALLOW_HEADERS", "*").split(",")

# Initialize FastAPI app
app = FastAPI(
    title="WhisperLive-NubemAI",
    description="Production-ready real-time audio transcription service",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
)

# Security
security = HTTPBearer()

# Client manager
client_manager = ClientManager(
    max_clients=MAX_CLIENTS,
    max_connection_time=MAX_CONNECTION_TIME
)


class LoginRequest(BaseModel):
    username: str
    password: str


class TranscriptionRequest(BaseModel):
    audio_data: str  # Base64 encoded audio
    language: Optional[str] = None
    model: Optional[str] = "base"


class TranscriptionResponse(BaseModel):
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration: float
    timestamp: str


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting WhisperLive-NubemAI server", 
                host=HOST, 
                port=PORT,
                max_clients=MAX_CLIENTS)
    
    # Initialize model loading here
    # TODO: Load Whisper models based on configuration
    
    # Start background tasks
    asyncio.create_task(monitor_resources())
    asyncio.create_task(cleanup_inactive_sessions())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down WhisperLive-NubemAI server")
    
    # Close all active connections
    for websocket in list(client_manager.clients.keys()):
        client_manager.remove_client(websocket)


async def monitor_resources():
    """Background task to monitor system resources"""
    while True:
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.update_resource_usage(cpu_percent=cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Queue sizes (if using queues)
            # metrics.update_queue_size("transcription", queue_size)
            
            logger.debug("Resource usage", 
                        cpu_percent=cpu_percent,
                        memory_percent=memory.percent)
            
        except Exception as e:
            logger.error("Error monitoring resources", error=str(e))
        
        await asyncio.sleep(30)  # Check every 30 seconds


async def cleanup_inactive_sessions():
    """Background task to cleanup inactive sessions"""
    while True:
        try:
            # Cleanup logic for inactive sessions
            current_time = time.time()
            for websocket, client in list(client_manager.clients.items()):
                start_time = client_manager.start_times.get(websocket, current_time)
                if current_time - start_time > MAX_CONNECTION_TIME:
                    logger.info("Removing inactive client", 
                               duration=current_time - start_time)
                    client_manager.remove_client(websocket)
                    await websocket.close(code=1000, reason="Session timeout")
            
        except Exception as e:
            logger.error("Error cleaning up sessions", error=str(e))
        
        await asyncio.sleep(60)  # Check every minute


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "WhisperLive-NubemAI",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    result = await health.check_health()
    status_code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(content=result, status_code=status_code)


@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    if not os.getenv("ENABLE_METRICS", "true").lower() == "true":
        raise HTTPException(status_code=404, detail="Metrics not enabled")
    
    return PlainTextResponse(
        content=metrics.get_metrics(),
        media_type="text/plain; version=0.0.4"
    )


@app.get("/stats")
@log_performance(component="api")
async def get_stats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get server statistics (requires authentication)"""
    # Verify token
    token = credentials.credentials
    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    stats = metrics.get_stats()
    stats.update({
        "active_clients": len(client_manager.clients),
        "max_clients": MAX_CLIENTS,
        "server_uptime": time.time() - metrics.start_time
    })
    
    return stats


@app.post("/auth/login")
@log_performance(component="auth")
async def login(request: LoginRequest):
    """Login endpoint to get JWT token"""
    # In production, verify against database
    # For demo, using simple check
    if request.username == "admin" and request.password == "admin":  # Change in production!
        access_token = auth_manager.create_access_token(
            data={"sub": request.username, "type": "user"}
        )
        
        return Token(
            access_token=access_token,
            expires_in=int(os.getenv("JWT_EXPIRATION_HOURS", "24")) * 3600
        )
    
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/auth/refresh")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Refresh JWT token"""
    token = credentials.credentials
    payload = auth_manager.verify_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Create new token
    access_token = auth_manager.create_access_token(
        data={"sub": payload.get("sub"), "type": payload.get("type")}
    )
    
    return Token(
        access_token=access_token,
        expires_in=int(os.getenv("JWT_EXPIRATION_HOURS", "24")) * 3600
    )


@app.post("/transcribe")
@log_performance(component="transcription")
async def transcribe_audio(
    request: TranscriptionRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """REST endpoint for audio transcription"""
    # Verify token
    token = credentials.credentials
    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Check rate limit
    client_id = payload.get("sub", "unknown")
    if not auth_manager.check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    start_time = time.time()
    
    try:
        # Decode audio data
        import base64
        audio_bytes = base64.b64decode(request.audio_data)
        
        # TODO: Process audio with Whisper model
        # For now, returning mock response
        result = {
            "text": "This is a mock transcription. Implement actual Whisper processing here.",
            "language": request.language or "en",
            "confidence": 0.95,
            "duration": time.time() - start_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Record metrics
        metrics.record_transcription(
            duration=result["duration"],
            model=request.model,
            language=result["language"],
            success=True
        )
        
        return TranscriptionResponse(**result)
    
    except Exception as e:
        logger.error("Transcription failed", error=str(e), exc_info=True)
        metrics.record_transcription(
            duration=time.time() - start_time,
            model=request.model,
            success=False
        )
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """WebSocket endpoint for real-time transcription"""
    await websocket.accept()
    
    client_id = None
    session_id = None
    
    try:
        # Authentication check
        auth_header = websocket.headers.get("Authorization")
        if os.getenv("ENABLE_AUTH", "true").lower() == "true":
            if not auth_header:
                await websocket.close(code=1008, reason="Missing authorization")
                return
            
            try:
                scheme, token = auth_header.split()
                if scheme.lower() != "bearer":
                    await websocket.close(code=1008, reason="Invalid authentication scheme")
                    return
                
                payload = auth_manager.verify_token(token)
                if not payload:
                    await websocket.close(code=1008, reason="Invalid or expired token")
                    return
                
                client_id = payload.get("sub", "unknown")
            
            except Exception as e:
                await websocket.close(code=1008, reason=f"Authentication error: {str(e)}")
                return
        else:
            client_id = websocket.client.host if websocket.client else "unknown"
        
        # Check rate limit
        if not auth_manager.check_rate_limit(client_id):
            await websocket.close(code=1008, reason="Rate limit exceeded")
            return
        
        # Check if server is full
        if len(client_manager.clients) >= MAX_CLIENTS:
            wait_time = client_manager.get_wait_time()
            await websocket.send_json({
                "type": "error",
                "message": f"Server full. Estimated wait time: {wait_time:.1f} minutes"
            })
            await websocket.close(code=1008, reason="Server full")
            return
        
        # Create session
        session_id = auth_manager.create_session(client_id, str(id(websocket)))
        
        # Initialize client
        # TODO: Initialize actual Whisper client here
        client = None  # Replace with actual client initialization
        
        # Add client to manager
        client_manager.add_client(websocket, client)
        metrics.record_connection("connect")
        
        logger.info("WebSocket client connected", 
                   client_id=client_id,
                   session_id=session_id,
                   active_clients=len(client_manager.clients))
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to WhisperLive-NubemAI"
        })
        
        # Handle messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                
                if message["type"] == "websocket.disconnect":
                    break
                
                # Update session activity
                auth_manager.update_session_activity(session_id)
                
                # Handle different message types
                if "bytes" in message:
                    # Audio data received
                    audio_data = message["bytes"]
                    metrics.record_audio_chunk(len(audio_data))
                    
                    # TODO: Process audio with Whisper
                    # For now, send mock response
                    await websocket.send_json({
                        "type": "transcription",
                        "text": "Processing audio...",
                        "partial": True
                    })
                
                elif "text" in message:
                    # Control message
                    data = json.loads(message["text"])
                    
                    if data.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    
                    elif data.get("type") == "config":
                        # Handle configuration updates
                        logger.info("Config update received", config=data)
                    
                    else:
                        logger.warning("Unknown message type", data=data)
            
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
            
            except WebSocketDisconnect:
                break
            
            except Exception as e:
                logger.error("Error handling WebSocket message", 
                           error=str(e),
                           client_id=client_id)
                metrics.record_error(error_type=type(e).__name__, component="websocket")
                break
    
    finally:
        # Cleanup
        if session_id:
            auth_manager.revoke_session(session_id)
        
        client_manager.remove_client(websocket)
        metrics.record_connection("disconnect")
        
        logger.info("WebSocket client disconnected",
                   client_id=client_id,
                   active_clients=len(client_manager.clients))


def create_ssl_context() -> Optional[ssl.SSLContext]:
    """Create SSL context for HTTPS/WSS"""
    if not ENABLE_SSL:
        return None
    
    if not SSL_CERT or not SSL_KEY:
        logger.error("SSL enabled but certificate/key not provided")
        return None
    
    if not Path(SSL_CERT).exists() or not Path(SSL_KEY).exists():
        logger.error("SSL certificate or key file not found")
        return None
    
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(SSL_CERT, SSL_KEY)
    return ssl_context


def run_server():
    """Run the enhanced server"""
    ssl_context = create_ssl_context()
    
    logger.info("Starting enhanced WhisperLive server",
               host=HOST,
               port=PORT,
               ssl=ENABLE_SSL,
               max_clients=MAX_CLIENTS)
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        ssl_keyfile=SSL_KEY if ENABLE_SSL else None,
        ssl_certfile=SSL_CERT if ENABLE_SSL else None,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        workers=1  # Single worker for WebSocket
    )


if __name__ == "__main__":
    run_server()