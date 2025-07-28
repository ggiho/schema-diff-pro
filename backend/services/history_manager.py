import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

from models.base import DatabaseConfig, ComparisonResult

logger = logging.getLogger(__name__)


class HistoryManager:
    """Manages comparison history in JSON file"""
    
    def __init__(self, history_file: str = "data/comparison_history.json"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        """Create history file if it doesn't exist"""
        if not self.history_file.exists():
            self._save_history([])
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load history from JSON file"""
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []
    
    def _save_history(self, history: List[Dict[str, Any]]):
        """Save history to JSON file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def add_comparison(self, 
                      comparison_id: str,
                      source_config: DatabaseConfig,
                      target_config: DatabaseConfig,
                      difference_count: int,
                      summary: Optional[Dict[str, int]] = None):
        """Add a new comparison to history"""
        history = self._load_history()
        
        # Create history entry
        entry = {
            "id": comparison_id,
            "timestamp": datetime.now().isoformat(),
            "source": {
                "host": source_config.host,
                "port": source_config.port,
                "database": source_config.database,
                "display_name": f"{source_config.host}:{source_config.port}/{source_config.database}"
            },
            "target": {
                "host": target_config.host,
                "port": target_config.port,
                "database": target_config.database,
                "display_name": f"{target_config.host}:{target_config.port}/{target_config.database}"
            },
            "difference_count": difference_count,
            "summary": summary or {}
        }
        
        # Add to beginning of list (most recent first)
        history.insert(0, entry)
        
        # Keep only last 20 comparisons
        history = history[:20]
        
        self._save_history(history)
        logger.info(f"Added comparison {comparison_id} to history")
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent comparisons"""
        history = self._load_history()
        return history[:limit]
    
    def get_by_id(self, comparison_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific comparison by ID"""
        history = self._load_history()
        for entry in history:
            if entry["id"] == comparison_id:
                return entry
        return None
    
    def clear_history(self):
        """Clear all history"""
        self._save_history([])
        logger.info("Cleared comparison history")