"""Insight extractor for memory analysis.

Provides:
- Entity recognition (people, places, tools)
- Sentiment analysis (user preferences)
- Abstraction and summarization (general knowledge)
- Pattern detection in conversations
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class EntityType(StrEnum):
    """Type of recognized entity."""

    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    TOOL = "tool"
    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    EVENT = "event"


class SentimentType(StrEnum):
    """Type of sentiment."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    PREFERENCE = "preference"


@dataclass
class Entity:
    """Recognized entity in conversation."""

    name: str
    entity_type: EntityType
    confidence: float  # 0.0 to 1.0
    context: str = ""
    first_seen: datetime = field(default_factory=datetime.now)
    mention_count: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "entity_type": self.entity_type.value,
            "confidence": self.confidence,
            "context": self.context,
            "mention_count": self.mention_count,
        }


@dataclass
class Sentiment:
    """Detected sentiment or preference."""

    sentiment_type: SentimentType
    target: str  # What the sentiment is about
    confidence: float
    evidence: str = ""
    intensity: float = 0.5  # 0.0 to 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sentiment_type": self.sentiment_type.value,
            "target": self.target,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "intensity": self.intensity,
        }


@dataclass
class Insight:
    """Extracted insight from conversation analysis."""

    insight_type: Literal["entity", "sentiment", "preference", "summary", "pattern"]
    content: str
    confidence: float
    source_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "insight_type": self.insight_type,
            "content": self.content,
            "confidence": self.confidence,
            "source_text": self.source_text,
            "metadata": self.metadata,
        }


@dataclass
class ExtractionResult:
    """Result of insight extraction from conversation."""

    entities: list[Entity] = field(default_factory=list)
    sentiments: list[Sentiment] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    summary: str = ""
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entities": [e.to_dict() for e in self.entities],
            "sentiments": [s.to_dict() for s in self.sentiments],
            "insights": [i.to_dict() for i in self.insights],
            "summary": self.summary,
            "topics": self.topics,
            "entity_count": len(self.entities),
            "sentiment_count": len(self.sentiments),
            "insight_count": len(self.insights),
        }


class InsightExtractor:
    """Extracts insights from conversation text.

    Performs:
    - Entity recognition
    - Sentiment analysis
    - Preference detection
    - Topic extraction
    - Summary generation
    """

    # Entity patterns for recognition
    PERSON_PATTERNS = [
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Capitalized two words (potential names)
        r"\b(?:我 | 你 | 他 | 她 | 它) (?:的)? (?:朋友 | 同事 | 领导 | 老板 | 老师 | 同学)\b",
    ]

    # Tool/technology keywords
    TOOL_KEYWORDS = {
        "python": ["python", "py", "pip", "python3"],
        "javascript": ["javascript", "js", "nodejs", "node.js", "npm"],
        "typescript": ["typescript", "ts", "tsc"],
        "react": ["react", "reactjs", "react.js"],
        "vue": ["vue", "vuejs", "vue.js"],
        "docker": ["docker", "dockerfile", "docker-compose"],
        "kubernetes": ["kubernetes", "k8s", "kubectl"],
        "git": ["git", "github", "gitlab", "gitee"],
        "vscode": ["vscode", "visual studio code"],
        "cursor": ["cursor"],
        "claude": ["claude", "anthropic"],
        "gpt": ["gpt", "chatgpt", "openai"],
        "fastapi": ["fastapi"],
        "django": ["django"],
        "flask": ["flask"],
    }

    # Technology keywords
    TECHNOLOGY_KEYWORDS = {
        "ai_ml": ["ai", "ml", "人工智能", "机器学习", "llm", "transformer", "neural network"],
        "web": ["web", "frontend", "backend", "api", "http", "rest", "graphql"],
        "database": ["database", "sql", "mysql", "postgresql", "mongodb", "redis"],
        "cloud": ["cloud", "aws", "azure", "gcp", "阿里云", "服务器"],
        "devops": ["ci/cd", "devops", "部署", "deploy", "pipeline"],
    }

    # Sentiment indicators
    POSITIVE_INDICATORS = [
        "喜欢", "爱", "好用", "好用", "推荐", "prefer", "like", "love",
        "good", "great", "excellent", "amazing", "helpful", "useful",
    ]

    NEGATIVE_INDICATORS = [
        "不喜欢", "讨厌", "难用", "差", "hate", "dislike", "bad", "terrible",
        "awful", "poor", "useless", "frustrating", "annoying",
    ]

    PREFERENCE_PATTERNS = [
        r"我 (?:更 | 比较) 喜欢\s*(.+?)(?:。|！|!) ",
        r"我 (?:习惯 | 一般) 用\s*(.+?)(?:。|！|!) ",
        r"我 (?:常用 | 经常用)\s*(.+?)(?:。|！|!) ",
        r"prefer\s*(.+?)\s*(?:to|over)",
        r"i (?:usually|always|tend to)\s*(.+?)(?:\.|!)",
    ]

    def __init__(self) -> None:
        self._compiled_patterns = {
            "person": [re.compile(p) for p in self.PERSON_PATTERNS],
            "preference": [re.compile(p, re.IGNORECASE) for p in self.PREFERENCE_PATTERNS],
        }

    def extract(self, text: str, context: str = "") -> ExtractionResult:
        """Extract insights from text.

        Args:
            text: Text to analyze
            context: Optional context for better understanding

        Returns:
            ExtractionResult with entities, sentiments, and insights
        """
        result = ExtractionResult()

        # Extract entities
        result.entities = self._extract_entities(text)

        # Extract sentiments
        result.sentiments = self._extract_sentiments(text)

        # Extract insights
        result.insights = self._extract_insights(text, result.entities, result.sentiments)

        # Extract topics
        result.topics = self._extract_topics(text)

        # Generate summary
        result.summary = self._generate_summary(text, result.entities, result.topics)

        return result

    def _extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text."""
        entities = []

        # Extract tools/technologies
        text_lower = text.lower()
        for tool_name, patterns in self.TOOL_KEYWORDS.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    entities.append(
                        Entity(
                            name=tool_name,
                            entity_type=EntityType.TOOL,
                            confidence=0.8,
                            context=f"Tool mentioned: {tool_name}",
                        )
                    )

        # Extract technologies
        for tech_category, keywords in self.TECHNOLOGY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    entities.append(
                        Entity(
                            name=tech_category,
                            entity_type=EntityType.TECHNOLOGY,
                            confidence=0.7,
                            context=f"Technology category: {tech_category}",
                        )
                    )

        # Extract person names (Chinese and Western)
        for pattern in self._compiled_patterns["person"]:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                # Filter out common false positives
                if match and len(match) > 1 and match not in ["我是", "你是", "他是"]:
                    entities.append(
                        Entity(
                            name=match,
                            entity_type=EntityType.PERSON,
                            confidence=0.6,
                            context="Person name detected",
                        )
                    )

        return entities

    def _extract_sentiments(self, text: str) -> list[Sentiment]:
        """Extract sentiments from text."""
        sentiments = []
        text_lower = text.lower()

        # Check for positive sentiment
        for indicator in self.POSITIVE_INDICATORS:
            if indicator.lower() in text_lower:
                # Try to find the target
                target = self._find_sentiment_target(text, indicator)
                sentiments.append(
                    Sentiment(
                        sentiment_type=SentimentType.POSITIVE,
                        target=target or "general",
                        confidence=0.7,
                        evidence=f"Contains positive indicator: {indicator}",
                        intensity=0.8,
                    )
                )

        # Check for negative sentiment
        for indicator in self.NEGATIVE_INDICATORS:
            if indicator.lower() in text_lower:
                target = self._find_sentiment_target(text, indicator)
                sentiments.append(
                    Sentiment(
                        sentiment_type=SentimentType.NEGATIVE,
                        target=target or "general",
                        confidence=0.7,
                        evidence=f"Contains negative indicator: {indicator}",
                        intensity=0.8,
                    )
                )

        # Check for preference patterns
        for pattern in self._compiled_patterns["preference"]:
            match = pattern.search(text)
            if match:
                target = match.group(1).strip() if match.lastindex else match.group(0)
                sentiments.append(
                    Sentiment(
                        sentiment_type=SentimentType.PREFERENCE,
                        target=target,
                        confidence=0.85,
                        evidence=f"Preference pattern matched: {match.group(0)}",
                        intensity=0.9,
                    )
                )

        return sentiments

    def _find_sentiment_target(self, text: str, indicator: str) -> str:
        """Find the target of a sentiment expression."""
        # Simple heuristic: look for nouns near the indicator
        idx = text.lower().find(indicator.lower())
        if idx == -1:
            return ""

        # Get surrounding context (20 chars before and after)
        start = max(0, idx - 20)
        end = min(len(text), idx + len(indicator) + 20)
        context = text[start:end]

        # Try to extract noun-like words (simplified)
        words = re.findall(r"[\u4e00-\u9fa5]{2,4}|[a-zA-Z]{3,15}", context)
        for word in words:
            if word.lower() != indicator.lower():
                return word

        return ""

    def _extract_insights(
        self,
        text: str,
        entities: list[Entity],
        sentiments: list[Sentiment],
    ) -> list[Insight]:
        """Extract insights from text based on entities and sentiments."""
        insights = []

        # Generate entity insights
        tool_mentions = [e for e in entities if e.entity_type == EntityType.TOOL]
        if len(tool_mentions) > 0:
            tools = [e.name for e in tool_mentions]
            insights.append(
                Insight(
                    insight_type="entity",
                    content=f"User works with: {', '.join(tools)}",
                    confidence=0.8,
                    source_text=text[:100],
                    metadata={"tools": tools},
                )
            )

        # Generate preference insights
        preferences = [s for s in sentiments if s.sentiment_type == SentimentType.PREFERENCE]
        for pref in preferences:
            insights.append(
                Insight(
                    insight_type="preference",
                    content=f"User prefers: {pref.target}",
                    confidence=pref.confidence,
                    source_text=text[:100],
                    metadata={"sentiment": pref.to_dict()},
                )
            )

        # Generate sentiment insights
        positive_count = sum(1 for s in sentiments if s.sentiment_type == SentimentType.POSITIVE)
        negative_count = sum(1 for s in sentiments if s.sentiment_type == SentimentType.NEGATIVE)

        if positive_count > negative_count and positive_count > 0:
            insights.append(
                Insight(
                    insight_type="sentiment",
                    content="User expressed positive sentiment",
                    confidence=0.7,
                    source_text=text[:100],
                    metadata={"sentiment": "positive", "count": positive_count},
                )
            )
        elif negative_count > positive_count and negative_count > 0:
            insights.append(
                Insight(
                    insight_type="sentiment",
                    content="User expressed negative sentiment",
                    confidence=0.7,
                    source_text=text[:100],
                    metadata={"sentiment": "negative", "count": negative_count},
                )
            )

        return insights

    def _extract_topics(self, text: str) -> list[str]:
        """Extract topics from text."""
        topics = []

        # Topic keywords
        topic_map = {
            "programming": ["代码", "编程", "function", "class", "def", "import", "code"],
            "ai_ml": ["ai", "ml", "模型", "training", "llm", "neural", "智能"],
            "web_dev": ["web", "frontend", "backend", "api", "http", "browser", "网站"],
            "devops": ["deploy", "docker", "server", "cloud", "ci/cd", "部署"],
            "database": ["database", "sql", "query", "数据", "表"],
            "career": ["工作", "career", "job", "面试", "升职"],
            "learning": ["学习", "learn", "study", "课程", "教程"],
        }

        text_lower = text.lower()
        for topic, keywords in topic_map.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if topic not in topics:
                        topics.append(topic)
                    break

        return topics[:5]  # Return top 5 topics

    def _generate_summary(
        self,
        text: str,
        entities: list[Entity],
        topics: list[str],
    ) -> str:
        """Generate a brief summary of the text."""
        # Simple extractive summary (first sentence + key entities)
        sentences = re.split(r"[.!?。！？]", text)
        first_sentence = sentences[0].strip() if sentences else text[:100]

        summary_parts = [first_sentence[:80]]

        if entities:
            tool_names = [e.name for e in entities if e.entity_type == EntityType.TOOL][:3]
            if tool_names:
                summary_parts.append(f"Mentions: {', '.join(tool_names)}")

        if topics:
            summary_parts.append(f"Topics: {', '.join(topics[:3])}")

        return " | ".join(summary_parts)

    def extract_batch(self, texts: list[str]) -> ExtractionResult:
        """Extract insights from multiple texts.

        Args:
            texts: List of texts to analyze

        Returns:
            Aggregated ExtractionResult
        """
        all_results = [self.extract(text) for text in texts]

        # Aggregate entities
        entity_map: dict[str, Entity] = {}
        for result in all_results:
            for entity in result.entities:
                if entity.name in entity_map:
                    entity_map[entity.name].mention_count += entity.mention_count
                else:
                    entity_map[entity.name] = entity

        # Aggregate sentiments
        all_sentiments = []
        for result in all_results:
            all_sentiments.extend(result.sentiments)

        # Aggregate insights
        all_insights = []
        for result in all_results:
            all_insights.extend(result.insights)

        # Aggregate topics
        topic_set: set[str] = set()
        for result in all_results:
            topic_set.update(result.topics)

        return ExtractionResult(
            entities=list(entity_map.values()),
            sentiments=all_sentiments,
            insights=all_insights,
            topics=list(topic_set),
            summary=f"Analyzed {len(texts)} messages",
        )


# Global extractor instance
_extractor: InsightExtractor | None = None


def get_extractor() -> InsightExtractor:
    """Get or create global insight extractor."""
    global _extractor
    if _extractor is None:
        _extractor = InsightExtractor()
    return _extractor


def extract_insights(text: str) -> ExtractionResult:
    """Extract insights from text using global extractor."""
    return get_extractor().extract(text)


def extract_insights_batch(texts: list[str]) -> ExtractionResult:
    """Extract insights from multiple texts."""
    return get_extractor().extract_batch(texts)
