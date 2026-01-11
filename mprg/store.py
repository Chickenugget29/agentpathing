"""MongoDB store for tasks, runs, and families."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import MongoClient


class MongoStore:
    """MongoDB-backed system-of-record for OmniPath."""

    def __init__(self, uri: Optional[str] = None, db_name: str = "mprg") -> None:
        uri = uri or os.getenv("MONGODB_URI")
        if not uri:
            uri = "mongodb://localhost:27017"
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.tasks = self.db.tasks
        self.runs = self.db.runs
        self.families = self.db.families
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.tasks.create_index("created_at")
        self.runs.create_index("task_id")
        self.families.create_index("task_id")

    def create_task(self, prompt: str) -> str:
        now = datetime.now(timezone.utc)
        result = self.tasks.insert_one(
            {
                "prompt": prompt,
                "status": "RUNNING",
                "created_at": now,
                "updated_at": now,
                "total_runs": 0,
                "valid_runs": 0,
                "family_count": 0,
                "robustness_status": None,
                "answers_agree": None,
            }
        )
        return str(result.inserted_id)

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        self.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": updates})

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        doc = self.tasks.find_one({"_id": ObjectId(task_id)})
        return _serialize(doc)

    def add_runs(self, task_id: str, runs: List[Dict[str, Any]]) -> None:
        if not runs:
            return
        self.runs.insert_many([{**run, "task_id": task_id} for run in runs])

    def get_runs(self, task_id: str) -> List[Dict[str, Any]]:
        docs = list(self.runs.find({"task_id": task_id}))
        return [_serialize(doc) for doc in docs]

    def clear_families(self, task_id: str) -> None:
        self.families.delete_many({"task_id": task_id})

    def add_families(self, task_id: str, families: List[Dict[str, Any]]) -> None:
        if not families:
            return
        self.families.insert_many([{**family, "task_id": task_id} for family in families])

    def get_families(self, task_id: str) -> List[Dict[str, Any]]:
        docs = list(self.families.find({"task_id": task_id}))
        return [_serialize(doc) for doc in docs]


def _serialize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    result = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
