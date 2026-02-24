"""Recent entities cache for tracking user operations.

This module provides short-term memory for tracking recently manipulated
objects like files, folders, etc. to enable contextual references like
"delete the folder I just created".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class RecentEntity:
    """A recently manipulated entity."""

    entity_type: Literal["file", "folder", "process", "text", "url", "other"]
    name: str
    action: Literal["create", "delete", "modify", "move", "copy", "open", "close"]
    location: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        """Return age in seconds."""
        return time.time() - self.timestamp

    @property
    def description(self) -> str:
        """Return a human-readable description."""
        location_part = f" at {self.location}" if self.location else ""
        return f"{self.action}d {self.entity_type}: {self.name}{location_part}"


class RecentEntitiesCache:
    """Cache for tracking recently manipulated entities.

    This provides short-term context awareness for the agent, allowing
    it to understand references like "the folder I just created" or
    "delete that file".

    Entities are automatically aged out after a configurable TTL.
    """

    def __init__(
        self,
        max_entities: int = 20,
        ttl_seconds: float = 300.0,  # 5 minutes default
    ) -> None:
        self._entities: list[RecentEntity] = []
        self._max_entities = max_entities
        self._ttl_seconds = ttl_seconds

    def add(
        self,
        entity_type: str,
        name: str,
        action: str,
        location: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> RecentEntity:
        """Add a new entity to the cache.

        Args:
            entity_type: Type of entity (file, folder, process, etc.)
            name: Name or identifier of the entity
            action: Action performed (create, delete, modify, etc.)
            location: Optional location path
            metadata: Optional additional metadata

        Returns:
            The created entity
        """
        entity = RecentEntity(
            entity_type=entity_type,  # type: ignore[arg-type]
            name=name,
            action=action,  # type: ignore[arg-type]
            location=location,
            metadata=metadata or {},
        )
        self._entities.append(entity)

        # Trim oldest entities if over limit
        while len(self._entities) > self._max_entities:
            self._entities.pop(0)

        return entity

    def get_recent(
        self,
        limit: int = 5,
        max_age_seconds: float | None = None,
        entity_type: str | None = None,
        action: str | None = None,
    ) -> list[RecentEntity]:
        """Get recent entities, optionally filtered.

        Args:
            limit: Maximum number of entities to return
            max_age_seconds: Only return entities newer than this age
            entity_type: Filter by entity type
            action: Filter by action type

        Returns:
            List of matching entities, newest first
        """
        self._cleanup_expired()

        result = self._entities.copy()

        # Apply filters
        if entity_type:
            result = [e for e in result if e.entity_type == entity_type]
        if action:
            result = [e for e in result if e.action == action]
        if max_age_seconds is not None:
            result = [e for e in result if e.age_seconds <= max_age_seconds]

        # Return newest first
        result.reverse()
        return result[:limit]

    def get_last(
        self,
        entity_type: str | None = None,
        action: str | None = None,
    ) -> RecentEntity | None:
        """Get the most recent entity, optionally filtered.

        Args:
            entity_type: Filter by entity type
            action: Filter by action type

        Returns:
            The most recent matching entity or None
        """
        results = self.get_recent(limit=1, entity_type=entity_type, action=action)
        return results[0] if results else None

    def find_by_name(self, name: str) -> RecentEntity | None:
        """Find an entity by name (case-insensitive).

        Args:
            name: Entity name to search for

        Returns:
            Matching entity or None
        """
        self._cleanup_expired()
        name_lower = name.lower()
        for entity in reversed(self._entities):
            if entity.name.lower() == name_lower:
                return entity
        return None

    def clear(self) -> None:
        """Clear all entities from the cache."""
        self._entities.clear()

    def _cleanup_expired(self) -> None:
        """Remove entities that have exceeded TTL."""
        self._entities = [
            e for e in self._entities if e.age_seconds <= self._ttl_seconds
        ]

    def get_context_summary(self, limit: int = 3) -> str:
        """Get a human-readable summary of recent entities.

        Args:
            limit: Maximum number of entities to summarize

        Returns:
            A summary string suitable for inclusion in prompts
        """
        recent = self.get_recent(limit=limit)
        if not recent:
            return "No recent file/folder operations."

        lines = ["Recent operations:"]
        for entity in recent:
            lines.append(f"  - {entity.description}")
        return "\n".join(lines)

    def to_prompts(self) -> str:
        """Generate a prompt section describing recent entities.

        Returns:
            Prompt text describing recent operations
        """
        self._cleanup_expired()

        if not self._entities:
            return ""

        lines = ["## Recent Context", ""]
        lines.append("The user has recently performed these actions:")
        lines.append("")

        for entity in self._entities[-5:]:  # Last 5 operations
            location_info = f" (at {entity.location})" if entity.location else ""
            lines.append(f"- {entity.action.capitalize()}d {entity.entity_type} called \"{entity.name}\"{location_info}")

        lines.append("")
        lines.append("When the user refers to 'the folder I just created' or 'that file',")
        lines.append("they are likely referring to one of these recent operations.")
        lines.append("")

        return "\n".join(lines)
