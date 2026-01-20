"""
Session Persistence API - Save, resume, and build on analyses across pages
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import uuid
import time
from datetime import datetime, timezone

from ..services.supabase_service import _supabase_select, _supabase_insert, _supabase_update
from ..config import get_api_flags
from ..middleware.auth_middleware import get_current_user, get_optional_user

router = APIRouter()

# Pydantic models
class SessionCreate(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    profile: str = "baseline"

class SessionItem(BaseModel):
    type: str  # insight|efficacy|dataset|note
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None

class SessionResponse(BaseModel):
    id: str
    title: Optional[str]
    profile: str
    context: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str
    item_count: int = 0

class SessionItemResponse(BaseModel):
    id: str
    type: str
    input: Optional[Dict[str, Any]]
    output: Optional[Dict[str, Any]]
    provenance: Optional[Dict[str, Any]]
    created_at: str

# Helper functions
def _get_session_id(x_session_id: Optional[str] = Header(None)) -> str:
    """Extract or generate session ID from header"""
    if x_session_id:
        return x_session_id
    return str(uuid.uuid4())

def _get_user_id(user: Optional[Dict[str, Any]] = Depends(get_optional_user)) -> Optional[str]:
    """Extract user ID from authenticated user (optional - allows anonymous sessions)"""
    return user.get("user_id") if user else None

def _get_idempotency_key(x_idempotency_key: Optional[str] = Header(None)) -> Optional[str]:
    """Extract idempotency key from header"""
    return x_idempotency_key

# Health check endpoint (must be before parameterized routes)
@router.get("/api/sessions/health")
async def sessions_health():
    """Health check for sessions API"""
    try:
        # Test Supabase connection
        await _supabase_select("user_sessions", ["count(*) as count"], limit=1)
        return {"status": "healthy", "service": "sessions"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Sessions service unhealthy: {e}")

@router.post("/api/sessions", response_model=SessionResponse)
async def create_or_update_session(
    session_data: SessionCreate,
    x_session_id: Optional[str] = Header(None),
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    x_idempotency_key: Optional[str] = Header(None)
):
    """Create or update a session with idempotency support"""
    try:
        session_id = session_data.id or _get_session_id(x_session_id)
        user_id = user.get("user_id") if user else None
        
        # Check if session exists
        existing = await _supabase_select(
            "user_sessions", 
            ["*"], 
            {"id": session_id}
        )
        
        current_time = datetime.now(timezone.utc).isoformat()
        
        if existing and len(existing) > 0:
            # Update existing session
            update_data = {
                "title": session_data.title or existing[0].get("title"),
                "context": session_data.context or existing[0].get("context"),
                "profile": session_data.profile,
                "updated_at": current_time
            }
            
            await _supabase_update(
                "user_sessions",
                {"id": session_id},
                update_data
            )
        else:
            # Create new session
            new_session = {
                "id": session_id,
                "user_id": user_id,
                "title": session_data.title or f"Session {session_id[:8]}",
                "profile": session_data.profile,
                "context": session_data.context or {},
                "created_at": current_time,
                "updated_at": current_time
            }
            
            await _supabase_insert("user_sessions", new_session)
        
        # Get item count
        items = await _supabase_select(
            "session_items",
            ["count(*) as count"],
            {"session_id": session_id}
        )
        item_count = items[0].get("count", 0) if items else 0
        
        return SessionResponse(
            id=session_id,
            title=session_data.title or f"Session {session_id[:8]}",
            profile=session_data.profile,
            context=session_data.context or {},
            created_at=current_time,
            updated_at=current_time,
            item_count=item_count
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session creation failed: {e}")

@router.get("/api/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Fetch a session with summary and last updated"""
    try:
        session = await _supabase_select(
            "user_sessions",
            ["*"],
            {"id": session_id}
        )
        
        if not session or len(session) == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session[0]
        
        # Get item count
        items = await _supabase_select(
            "session_items",
            ["count(*) as count"],
            {"session_id": session_id}
        )
        item_count = items[0].get("count", 0) if items else 0
        
        return SessionResponse(
            id=session_data["id"],
            title=session_data.get("title"),
            profile=session_data.get("profile", "baseline"),
            context=session_data.get("context", {}),
            created_at=session_data["created_at"],
            updated_at=session_data["updated_at"],
            item_count=item_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session retrieval failed: {e}")

@router.get("/api/sessions", response_model=Dict[str, List[SessionResponse]])
async def list_sessions(
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    limit: int = 20,
    offset: int = 0
):
    """List recent sessions for current user (paginated)"""
    try:
        user_id = user.get("user_id") if user else None
        
        # Build query conditions
        conditions = {}
        if user_id:
            conditions["user_id"] = user_id
        
        sessions = await _supabase_select(
            "user_sessions",
            ["*"],
            conditions,
            limit=limit
        )
        
        # Get item counts for each session
        session_responses = []
        for session in sessions:
            items = await _supabase_select(
                "session_items",
                ["count(*) as count"],
                {"session_id": session["id"]}
            )
            item_count = items[0].get("count", 0) if items else 0
            
            session_responses.append(SessionResponse(
                id=session["id"],
                title=session.get("title"),
                profile=session.get("profile", "baseline"),
                context=session.get("context", {}),
                created_at=session["created_at"],
                updated_at=session["updated_at"],
                item_count=item_count
            ))
        
        return {"items": session_responses}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session listing failed: {e}")

@router.post("/api/sessions/{session_id}/items", response_model=Dict[str, str])
async def append_session_item(
    session_id: str,
    item: SessionItem,
    x_idempotency_key: Optional[str] = Header(None)
):
    """Append a session item (insight|efficacy|dataset|note)"""
    try:
        # Verify session exists
        session = await _supabase_select(
            "user_sessions",
            ["id"],
            {"id": session_id}
        )
        
        if not session or len(session) == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Create session item
        item_id = str(uuid.uuid4())
        current_time = datetime.now(timezone.utc).isoformat()
        
        new_item = {
            "id": item_id,
            "session_id": session_id,
            "type": item.type,
            "input": item.input or {},
            "output": item.output or {},
            "provenance": item.provenance or {},
            "created_at": current_time
        }
        
        await _supabase_insert("session_items", new_item)
        
        # Update session timestamp
        await _supabase_update(
            "user_sessions",
            {"id": session_id},
            {"updated_at": current_time}
        )
        
        return {"id": item_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Item append failed: {e}")

@router.get("/api/sessions/{session_id}/items", response_model=Dict[str, List[SessionItemResponse]])
async def list_session_items(
    session_id: str,
    type_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List items in a session (filter by type optional)"""
    try:
        # Verify session exists
        session = await _supabase_select(
            "user_sessions",
            ["id"],
            {"id": session_id}
        )
        
        if not session or len(session) == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Build query conditions
        conditions = {"session_id": session_id}
        if type_filter:
            conditions["type"] = type_filter
        
        items = await _supabase_select(
            "session_items",
            ["*"],
            conditions,
            limit=limit
        )
        
        item_responses = [
            SessionItemResponse(
                id=item["id"],
                type=item["type"],
                input=item.get("input"),
                output=item.get("output"),
                provenance=item.get("provenance"),
                created_at=item["created_at"]
            )
            for item in items
        ]
        
        return {"items": item_responses}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Item listing failed: {e}")

