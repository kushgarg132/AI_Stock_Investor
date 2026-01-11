from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from backend.database import get_database

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self.collection_name = "agent_memories"

    async def add_memory(self, symbol: str, content: str, decision: str, memory_type: str = "analysis", metadata: Dict = None):
        """
        Adds a new memory entry to the database.
        """
        db = await get_database()
        if db is None:
            logger.warning("Database connection not available. Memory skipped.")
            return

        memory_entry = {
            "symbol": symbol.upper(),
            "content": content,
            "decision": decision,
            "type": memory_type,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow()
        }
        
        try:
            result = await db[self.collection_name].insert_one(memory_entry)
            logger.info(f"Memory added for {symbol}: {result.inserted_id}")
        except Exception as e:
            logger.error(f"Failed to add memory for {symbol}: {e}")

    async def get_memories(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        Retrieves the most recent memories for a specific symbol.
        """
        db = await get_database()
        if db is None:
            logger.warning("Database connection not available. Cannot retrieve memories.")
            return []

        try:
            cursor = db[self.collection_name].find(
                {"symbol": symbol.upper()}
            ).sort("timestamp", -1).limit(limit)
            
            memories = await cursor.to_list(length=limit)
            return memories
        except Exception as e:
            logger.error(f"Failed to retrieve memories for {symbol}: {e}")
            return []

    async def cleanup_old_memories(self, days: int = 30):
        """
        Optional: Remove memories older than X days to keep context relevant.
        """
        # Logic to delete old entries can be added here
        pass

memory_manager = MemoryManager()
