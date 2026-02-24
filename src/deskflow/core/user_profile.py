"""User profile system for personalized AI responses.

Provides:
- User preference storage and learning
- Trait extraction from conversations
- Personalized response generation
- User behavior analysis
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UserTrait:
    """A detected user trait or preference."""

    name: str
    category: Literal["communication", "technical", "personal", "work", "preference"]
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    occurrence_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "occurrence_count": self.occurrence_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserTrait:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            category=data["category"],
            confidence=data["confidence"],
            evidence=data.get("evidence", []),
            created_at=data.get("created_at", time.time()),
            last_updated=data.get("last_updated", time.time()),
            occurrence_count=data.get("occurrence_count", 1),
        )


@dataclass
class UserProfile:
    """Complete user profile with preferences and traits."""

    # Basic info
    name: str | None = None
    email: str | None = None
    timezone: str = "UTC"
    language: str = "zh-CN"

    # Communication preferences
    response_style: Literal["concise", "detailed", "technical", "casual"] = "detailed"
    code_language_preference: str = "python"
    explanation_depth: Literal["beginner", "intermediate", "expert"] = "intermediate"

    # Detected traits
    traits: dict[str, UserTrait] = field(default_factory=dict)

    # Interaction statistics
    total_interactions: int = 0
    favorite_topics: list[str] = field(default_factory=list)
    avoided_topics: list[str] = field(default_factory=list)

    # Learning metadata
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    last_interaction: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "email": self.email,
            "timezone": self.timezone,
            "language": self.language,
            "response_style": self.response_style,
            "code_language_preference": self.code_language_preference,
            "explanation_depth": self.explanation_depth,
            "traits": {k: v.to_dict() for k, v in self.traits.items()},
            "total_interactions": self.total_interactions,
            "favorite_topics": self.favorite_topics,
            "avoided_topics": self.avoided_topics,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "last_interaction": self.last_interaction,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserProfile:
        """Create from dictionary."""
        traits = {}
        for key, trait_data in data.get("traits", {}).items():
            traits[key] = UserTrait.from_dict(trait_data)

        return cls(
            name=data.get("name"),
            email=data.get("email"),
            timezone=data.get("timezone", "UTC"),
            language=data.get("language", "zh-CN"),
            response_style=data.get("response_style", "detailed"),
            code_language_preference=data.get("code_language_preference", "python"),
            explanation_depth=data.get("explanation_depth", "intermediate"),
            traits=traits,
            total_interactions=data.get("total_interactions", 0),
            favorite_topics=data.get("favorite_topics", []),
            avoided_topics=data.get("avoided_topics", []),
            created_at=data.get("created_at", time.time()),
            last_updated=data.get("last_updated", time.time()),
            last_interaction=data.get("last_interaction", time.time()),
        )


class TraitMiner:
    """Extracts user traits from conversation history.

    Detects:
    - Communication style preferences
    - Technical expertise level
    - Topic interests
    - Behavioral patterns
    """

    # Keyword patterns for trait detection
    COMMUNICATION_PATTERNS = {
        "concise": ["简短", "简洁", "直接", "快点", "summary", "brief", "concise"],
        "detailed": ["详细", "解释", "为什么", "how", "why", "detailed", "explain"],
        "technical": ["代码", "实现", "技术", "algorithm", "code", "technical", "implement"],
        "casual": ["随便", "聊天", "hi", "hello", "hey", "casual"],
    }

    TECHNICAL_PATTERNS = {
        "python": ["python", "py", "pip", "django", "flask", "fastapi"],
        "javascript": ["javascript", "js", "node", "npm", "react", "vue", "typescript"],
        "go": ["golang", "go ", "goroutine", "gomod"],
        "rust": ["rust", "cargo", "rustc", "borrow checker"],
        "devops": ["docker", "k8s", "kubernetes", "ci/cd", "deploy", "linux"],
    }

    EXPERTISE_INDICATORS = {
        "beginner": ["什么是", "怎么开始", "新手", "入门", "beginner", "how to start", "what is"],
        "intermediate": ["如何优化", "最佳实践", "比较", "intermediate", "best practice", "compare"],
        "expert": ["底层原理", "源码", "架构设计", "expert", "internals", "architecture", "source code"],
    }

    def __init__(self) -> None:
        self._mined_traits: dict[str, UserTrait] = {}

    def analyze_message(self, message: str, role: str = "user") -> list[UserTrait]:
        """Analyze a single message and extract traits.

        Args:
            message: The message content to analyze.
            role: Message role (user/assistant).

        Returns:
            List of detected traits.
        """
        if role != "user":
            return []

        traits = []
        message_lower = message.lower()

        # Detect communication style
        traits.extend(self._detect_communication_style(message_lower))

        # Detect technical preferences
        traits.extend(self._detect_technical_preference(message_lower))

        # Detect expertise level
        traits.extend(self._detect_expertise_level(message_lower))

        return traits

    def _detect_communication_style(self, text: str) -> list[UserTrait]:
        """Detect user's preferred communication style."""
        traits = []
        style_scores: dict[str, int] = {style: 0 for style in self.COMMUNICATION_PATTERNS}

        for style, patterns in self.COMMUNICATION_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text:
                    style_scores[style] += 1

        # Find dominant style
        max_style = max(style_scores, key=style_scores.get)
        if style_scores[max_style] > 0:
            traits.append(
                UserTrait(
                    name=f"prefers_{max_style}_responses",
                    category="communication",
                    confidence=min(0.5 + style_scores[max_style] * 0.15, 0.95),
                    evidence=[f"Detected in message: {max_style} keywords"],
                )
            )

        return traits

    def _detect_technical_preference(self, text: str) -> list[UserTrait]:
        """Detect user's preferred programming language or technology."""
        traits = []
        tech_scores: dict[str, int] = {tech: 0 for tech in self.TECHNICAL_PATTERNS}

        for tech, patterns in self.TECHNICAL_PATTERNS.items():
            for pattern in patterns:
                # Use word boundary matching for tech terms
                if re.search(rf"\b{re.escape(pattern)}\b", text, re.IGNORECASE):
                    tech_scores[tech] += 1

        # Find technologies mentioned
        for tech, score in tech_scores.items():
            if score > 0:
                traits.append(
                    UserTrait(
                        name=f"uses_{tech}",
                        category="technical",
                        confidence=min(0.4 + score * 0.2, 0.9),
                        evidence=[f"Mentioned {tech} related terms"],
                    )
                )

        return traits

    def _detect_expertise_level(self, text: str) -> list[UserTrait]:
        """Detect user's technical expertise level."""
        traits = []
        level_scores: dict[str, int] = {level: 0 for level in self.EXPERTISE_INDICATORS}

        for level, patterns in self.EXPERTISE_INDICATORS.items():
            for pattern in patterns:
                if pattern.lower() in text:
                    level_scores[level] += 1

        # Find dominant level
        max_level = max(level_scores, key=level_scores.get)
        if level_scores[max_level] > 0:
            traits.append(
                UserTrait(
                    name=f"expertise_{max_level}",
                    category="technical",
                    confidence=min(0.5 + level_scores[max_level] * 0.15, 0.9),
                    evidence=[f"Shows {max_level} level indicators"],
                )
            )

        return traits

    def aggregate_traits(self, messages: list[dict[str, str]]) -> dict[str, UserTrait]:
        """Aggregate traits from multiple messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            Dictionary of aggregated traits by name.
        """
        all_traits: dict[str, UserTrait] = {}

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "user")

            traits = self.analyze_message(content, role)

            for trait in traits:
                if trait.name in all_traits:
                    # Update existing trait
                    existing = all_traits[trait.name]
                    existing.confidence = min(existing.confidence + 0.1, 0.95)
                    existing.evidence.extend(trait.evidence)
                    existing.occurrence_count += 1
                    existing.last_updated = time.time()
                else:
                    all_traits[trait.name] = trait

        return all_traits


class UserProfileManager:
    """Manages user profile persistence and updates.

    Features:
    - Load/save profile to disk
    - Incremental trait learning
    - Preference updates
    - Interaction tracking
    """

    def __init__(self, profile_dir: str | Path | None = None) -> None:
        self._profile_dir = Path(profile_dir) if profile_dir else Path.cwd() / "data" / "user"
        self._profile_path = self._profile_dir / "profile.json"
        self._profile: UserProfile | None = None
        self._trait_miner = TraitMiner()

    async def load_profile(self) -> UserProfile:
        """Load user profile from disk or create new one."""
        if self._profile:
            return self._profile

        if self._profile_path.exists():
            try:
                with open(self._profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profile = UserProfile.from_dict(data)
                logger.info("user_profile_loaded", path=str(self._profile_path))
            except Exception as e:
                logger.warning("profile_load_failed", error=str(e))
                self._profile = self._create_default_profile()
        else:
            self._profile = self._create_default_profile()

        return self._profile

    async def save_profile(self) -> Path:
        """Save current profile to disk."""
        if not self._profile:
            raise RuntimeError("No profile loaded")

        self._profile.last_updated = time.time()
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        with open(self._profile_path, "w", encoding="utf-8") as f:
            json.dump(self._profile.to_dict(), f, indent=2, ensure_ascii=False)

        logger.info("user_profile_saved", path=str(self._profile_path))
        return self._profile_path

    def _create_default_profile(self) -> UserProfile:
        """Create a default user profile."""
        return UserProfile(
            name=None,
            email=None,
            timezone="Asia/Shanghai",
            language="zh-CN",
            response_style="detailed",
            code_language_preference="python",
            explanation_depth="intermediate",
        )

    async def update_basic_info(
        self,
        name: str | None = None,
        email: str | None = None,
        timezone: str | None = None,
        language: str | None = None,
    ) -> UserProfile:
        """Update basic user information."""
        if not self._profile:
            await self.load_profile()

        if name is not None:
            self._profile.name = name
        if email is not None:
            self._profile.email = email
        if timezone is not None:
            self._profile.timezone = timezone
        if language is not None:
            self._profile.language = language

        await self.save_profile()
        return self._profile

    async def update_preferences(
        self,
        response_style: Literal["concise", "detailed", "technical", "casual"] | None = None,
        code_language: str | None = None,
        explanation_depth: Literal["beginner", "intermediate", "expert"] | None = None,
    ) -> UserProfile:
        """Update user preferences."""
        if not self._profile:
            await self.load_profile()

        if response_style is not None:
            self._profile.response_style = response_style
        if code_language is not None:
            self._profile.code_language_preference = code_language
        if explanation_depth is not None:
            self._profile.explanation_depth = explanation_depth

        await self.save_profile()
        return self._profile

    async def learn_from_conversation(
        self,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Learn traits from a conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'.

        Returns:
            Learning result with detected traits.
        """
        if not self._profile:
            await self.load_profile()

        # Extract new traits
        new_traits = self._trait_miner.aggregate_traits(messages)

        # Update profile traits
        updated_count = 0
        for trait_name, new_trait in new_traits.items():
            if trait_name in self._profile.traits:
                # Merge with existing trait
                existing = self._profile.traits[trait_name]
                existing.confidence = min(existing.confidence + 0.05, 0.95)
                existing.occurrence_count += new_trait.occurrence_count
                existing.last_updated = time.time()
                if len(existing.evidence) < 10:  # Keep max 10 evidence items
                    existing.evidence.extend(new_trait.evidence[:3])
            else:
                # Add new trait
                self._profile.traits[trait_name] = new_trait
                updated_count += 1

        # Update interaction count
        self._profile.total_interactions += 1
        self._profile.last_interaction = time.time()

        # Update favorite topics
        self._update_favorite_topics(messages)

        # Save profile
        await self.save_profile()

        return {
            "traits_detected": len(new_traits),
            "new_traits": updated_count,
            "total_traits": len(self._profile.traits),
            "detected_traits": [t.name for t in new_traits.values()],
        }

    def _update_favorite_topics(self, messages: list[dict[str, str]]) -> None:
        """Update favorite topics based on conversation."""
        if not self._profile:
            return

        # Simple topic detection based on keywords
        topic_keywords = {
            "programming": ["code", "编程", "function", "class", "def", "import"],
            "ai_ml": ["ai", "ml", "模型", "training", "llm", "neural"],
            "web_dev": ["web", "frontend", "backend", "api", "http", "browser"],
            "devops": ["deploy", "docker", "server", "cloud", "ci/cd"],
            "data": ["data", "数据库", "sql", "analytics", "query"],
        }

        topic_counts: dict[str, int] = {}

        for msg in messages:
            content = msg.get("content", "").lower()
            for topic, keywords in topic_keywords.items():
                for keyword in keywords:
                    if keyword.lower() in content:
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # Update favorite topics (top 3)
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
        new_favorites = [topic for topic, _ in sorted_topics[:3] if topic not in self._profile.avoided_topics]

        for topic in new_favorites:
            if topic not in self._profile.favorite_topics:
                self._profile.favorite_topics.append(topic)
                if len(self._profile.favorite_topics) > 5:
                    self._profile.favorite_topics.pop(0)

    async def get_personalization_context(self) -> dict[str, Any]:
        """Get personalization context for response generation.

        Returns:
            Context dictionary for prompt customization.
        """
        if not self._profile:
            await self.load_profile()

        # Get top traits by confidence
        top_traits = sorted(
            self._profile.traits.values(),
            key=lambda t: t.confidence,
            reverse=True,
        )[:5]

        return {
            "user_name": self._profile.name,
            "response_style": self._profile.response_style,
            "explanation_depth": self._profile.explanation_depth,
            "code_language": self._profile.code_language_preference,
            "timezone": self._profile.timezone,
            "favorite_topics": self._profile.favorite_topics,
            "top_traits": [t.name for t in top_traits],
        }

    def get_stats(self) -> dict[str, Any]:
        """Get profile statistics."""
        if not self._profile:
            return {"loaded": False}

        # Count traits by category
        traits_by_category: dict[str, int] = {}
        for trait in self._profile.traits.values():
            cat = trait.category
            traits_by_category[cat] = traits_by_category.get(cat, 0) + 1

        return {
            "loaded": True,
            "total_interactions": self._profile.total_interactions,
            "total_traits": len(self._profile.traits),
            "traits_by_category": traits_by_category,
            "favorite_topics": self._profile.favorite_topics,
            "last_interaction": datetime.fromtimestamp(
                self._profile.last_interaction
            ).isoformat()
            if self._profile.last_interaction
            else None,
        }


# Global instance
_profile_manager: UserProfileManager | None = None


def get_profile_manager(profile_dir: str | Path | None = None) -> UserProfileManager:
    """Get or create global profile manager."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = UserProfileManager(profile_dir)
    return _profile_manager
