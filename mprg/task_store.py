"""MongoDB persistence for tasks and runs."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import MongoClient


class TaskStore:
    """MongoDB-backed storage for tasks and runs."""

    def __init__(self, uri: Optional[str] = None, db_name: str = "mprg") -> None:
        uri = uri or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.tasks = self.db.tasks
        self.runs = self.db.runs
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.tasks.create_index("created_at")
        self.tasks.create_index("status")
        self.runs.create_index("task_id")
        self.runs.create_index("agent_role")
        self.runs.create_index("created_at")

    def create_task(self, input_text: str) -> str:
        now = datetime.now(timezone.utc)
        result = self.tasks.insert_one(
            {
                "input_text": input_text,
                "status": "NEW",
                "robustness_status": None,
                "num_families": None,
                "created_at": now,
                "updated_at": now,
            }
        )
        return str(result.inserted_id)

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> None:
        updates["updated_at"] = datetime.now(timezone.utc)
        self.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": updates})

    def insert_run(self, task_id: str, run_doc: Dict[str, Any]) -> str:
        doc = {**run_doc, "task_id": task_id, "created_at": datetime.now(timezone.utc)}
        result = self.runs.insert_one(doc)
        return str(result.inserted_id)

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        doc = self.tasks.find_one({"_id": ObjectId(task_id)})
        return _serialize(doc)

    def get_runs(self, task_id: str) -> List[Dict[str, Any]]:
        docs = list(self.runs.find({"task_id": task_id}).sort("created_at", 1))
        return [_serialize(doc) for doc in docs]

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        docs = list(self.tasks.find().sort("created_at", -1).limit(limit))
        return [_serialize(doc) for doc in docs]


def _serialize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    result: Dict[str, Any] = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
