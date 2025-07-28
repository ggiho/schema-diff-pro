from fastapi import APIRouter, HTTPException
from typing import List, Optional
import uuid
from datetime import datetime

from models.base import ComparisonProfile

router = APIRouter()

# In-memory storage for profiles (in production, use database)
profiles_storage: dict[str, ComparisonProfile] = {}


@router.post("/", response_model=ComparisonProfile)
async def create_profile(profile: ComparisonProfile) -> ComparisonProfile:
    """Create a new comparison profile"""
    if not profile.id:
        profile.id = str(uuid.uuid4())
    
    profile.created_at = datetime.now()
    profiles_storage[profile.id] = profile
    
    return profile


@router.get("/", response_model=List[ComparisonProfile])
async def list_profiles(
    skip: int = 0,
    limit: int = 100
) -> List[ComparisonProfile]:
    """List all comparison profiles"""
    profiles = list(profiles_storage.values())
    return profiles[skip : skip + limit]


@router.get("/{profile_id}", response_model=ComparisonProfile)
async def get_profile(profile_id: str) -> ComparisonProfile:
    """Get a specific profile"""
    if profile_id not in profiles_storage:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return profiles_storage[profile_id]


@router.put("/{profile_id}", response_model=ComparisonProfile)
async def update_profile(
    profile_id: str,
    profile: ComparisonProfile
) -> ComparisonProfile:
    """Update a profile"""
    if profile_id not in profiles_storage:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    existing = profiles_storage[profile_id]
    profile.id = profile_id
    profile.created_at = existing.created_at
    profile.updated_at = datetime.now()
    
    profiles_storage[profile_id] = profile
    
    return profile


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str) -> dict:
    """Delete a profile"""
    if profile_id not in profiles_storage:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    del profiles_storage[profile_id]
    
    return {"status": "deleted", "profile_id": profile_id}


@router.post("/{profile_id}/run")
async def run_profile_comparison(profile_id: str) -> dict:
    """Run a comparison using a saved profile"""
    if profile_id not in profiles_storage:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile = profiles_storage[profile_id]
    
    # Import here to avoid circular import
    from .comparison import start_comparison
    from fastapi import BackgroundTasks
    
    # Update last run time
    profile.last_run = datetime.now()
    profiles_storage[profile_id] = profile
    
    # Start comparison
    result = await start_comparison(
        source_config=profile.source_config,
        target_config=profile.target_config,
        options=profile.comparison_options,
        background_tasks=BackgroundTasks()
    )
    
    return {
        **result,
        "profile_id": profile_id,
        "profile_name": profile.name
    }