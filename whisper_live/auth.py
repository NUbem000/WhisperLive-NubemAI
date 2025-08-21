"""
Authentication and Authorization module for WhisperLive
Implements JWT-based authentication with rate limiting
"""

import os
import time
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
import redis
from slowapi import Limiter
from slowapi.util import get_remote_address

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
API_KEY = os.getenv("API_KEY")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "true").lower() == "true"

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis client for rate limiting and session management
redis_client = None
if os.getenv("ENABLE_CACHE", "true").lower() == "true":
    try:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True
        )
        redis_client.ping()
    except:
        print("Warning: Redis not available, falling back to in-memory storage")
        redis_client = None

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[os.getenv("RATE_LIMIT_REQUESTS", "100") + "/minute"]
)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class User(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = False


class UserInDB(User):
    hashed_password: str


class AuthManager:
    """Manages authentication and authorization"""
    
    def __init__(self):
        self.sessions = {}
        self.rate_limits = {}
        
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key"""
        if not API_KEY:
            return True  # No API key configured, allow all
        return secrets.compare_digest(api_key, API_KEY)
    
    def check_rate_limit(self, client_id: str, max_requests: int = 100, window: int = 60) -> bool:
        """Check if client has exceeded rate limit"""
        if not redis_client:
            # Fallback to in-memory rate limiting
            current_time = time.time()
            if client_id not in self.rate_limits:
                self.rate_limits[client_id] = []
            
            # Clean old requests
            self.rate_limits[client_id] = [
                req_time for req_time in self.rate_limits[client_id]
                if current_time - req_time < window
            ]
            
            if len(self.rate_limits[client_id]) >= max_requests:
                return False
            
            self.rate_limits[client_id].append(current_time)
            return True
        
        # Redis-based rate limiting
        key = f"rate_limit:{client_id}"
        try:
            current = redis_client.incr(key)
            if current == 1:
                redis_client.expire(key, window)
            return current <= max_requests
        except:
            return True  # Allow on Redis error
    
    def create_session(self, user_id: str, websocket_id: str) -> str:
        """Create a new session"""
        session_id = secrets.token_urlsafe(32)
        session_data = {
            "user_id": user_id,
            "websocket_id": websocket_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        
        if redis_client:
            key = f"session:{session_id}"
            redis_client.hset(key, mapping=session_data)
            redis_client.expire(key, 3600 * 24)  # 24 hours
        else:
            self.sessions[session_id] = session_data
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        if redis_client:
            key = f"session:{session_id}"
            data = redis_client.hgetall(key)
            return data if data else None
        else:
            return self.sessions.get(session_id)
    
    def update_session_activity(self, session_id: str):
        """Update last activity time for a session"""
        if redis_client:
            key = f"session:{session_id}"
            redis_client.hset(key, "last_activity", datetime.utcnow().isoformat())
            redis_client.expire(key, 3600 * 24)  # Reset expiry
        else:
            if session_id in self.sessions:
                self.sessions[session_id]["last_activity"] = datetime.utcnow().isoformat()
    
    def revoke_session(self, session_id: str):
        """Revoke a session"""
        if redis_client:
            key = f"session:{session_id}"
            redis_client.delete(key)
        else:
            self.sessions.pop(session_id, None)


# Global auth manager instance
auth_manager = AuthManager()


def require_auth(f):
    """Decorator to require authentication for websocket handlers"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if not ENABLE_AUTH:
            return await f(*args, **kwargs)
        
        # Extract websocket from args
        websocket = args[0] if args else kwargs.get('websocket')
        if not websocket:
            raise ValueError("No websocket found in arguments")
        
        # Check for authorization header
        auth_header = websocket.request_headers.get('Authorization')
        if not auth_header:
            await websocket.close(code=1008, reason="Missing authorization")
            return
        
        # Verify token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != 'bearer':
                await websocket.close(code=1008, reason="Invalid authentication scheme")
                return
            
            payload = auth_manager.verify_token(token)
            if not payload:
                await websocket.close(code=1008, reason="Invalid or expired token")
                return
            
            # Add user info to websocket
            websocket.user = payload
            return await f(*args, **kwargs)
            
        except Exception as e:
            await websocket.close(code=1008, reason=f"Authentication error: {str(e)}")
            return
    
    return decorated_function


def require_api_key(f):
    """Decorator to require API key for HTTP endpoints"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        if not ENABLE_AUTH or not API_KEY:
            return await f(*args, **kwargs)
        
        # Extract request from args
        request = args[0] if args else kwargs.get('request')
        if not request:
            raise ValueError("No request found in arguments")
        
        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if not api_key or not auth_manager.verify_api_key(api_key):
            return {"error": "Invalid API key"}, 401
        
        return await f(*args, **kwargs)
    
    return decorated_function