"""Proactive greeting engine for DeskFlow Agent.

Generates context-aware greeting messages based on:
- Time of day
- Day of week
- Recent conversation history
- User preferences
- Special occasions
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Any

from deskflow.observability.logging import get_logger

logger = get_logger(__name__)


class GreetingType(str, Enum):
    """Type of greeting message."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    WEEKEND = "weekend"
    MONDAY = "monday"
    FRIDAY = "friday"
    SPECIAL = "special"


@dataclass
class GreetingContext:
    """Context information for generating a greeting."""

    hour: int
    day_of_week: int  # 0=Monday, 6=Sunday
    day_of_year: int
    is_weekend: bool
    is_workday: bool
    recent_tasks_completed: int = 0
    last_interaction_hours_ago: float | None = None
    user_name: str | None = None


@dataclass
class GreetingResult:
    """Result of generating a greeting."""

    message: str
    greeting_type: GreetingType
    context_used: dict[str, Any]


class ProactiveGreeter:
    """Generate proactive, context-aware greetings.

    Features:
    - Time-aware greetings (morning/afternoon/evening/night)
    - Day-aware greetings (Monday motivation, Friday excitement, weekend vibes)
    - Personalization with user name
    - Context awareness (recent activity, last interaction)
    - Special occasion recognition (birthdays, holidays - configurable)
    """

    # Special dates (month, day) -> message
    SPECIAL_DATES: dict[tuple[int, int], str] = {
        (1, 1): "Happy New Year! Wishing you a productive and successful year ahead!",
        (12, 25): "Merry Christmas! Hope you're having a wonderful holiday!",
        (10, 1): "Happy National Day! Enjoy the holiday!",
        (5, 1): "Happy Labor Day! Time to relax and recharge!",
        (1, 21): "Happy Chinese New Year's Eve! Wishing you prosperity!",
    }

    # Monday motivation messages
    MONDAY_MESSAGES: list[str] = [
        "Good morning! It's Monday - a fresh start to a new week. What goals shall we tackle together?",
        "Happy Monday! New week, new opportunities. How can I help you make today productive?",
        "Monday motivation activated! Let's make this week amazing. What's first on your list?",
    ]

    # Friday celebration messages
    FRIDAY_MESSAGES: list[str] = [
        "Happy Friday! You made it through the week! What's the plan for celebrating?",
        "TGIF! Another productive week in the books. How can I help you wrap things up?",
        "Friday feels! Weekend is almost here. What shall we accomplish before then?",
    ]

    # Weekend messages
    WEEKEND_MESSAGES: list[str] = [
        "Good {time}! It's the weekend - time to relax and recharge. Need help with anything?",
        "Weekend vibes! Whether you're working or resting, I'm here to help.",
        "Happy {day}! Hope you're enjoying your weekend. Anything I can assist with?",
    ]

    # Time-based greetings
    TIME_GREETINGS: dict[str, list[str]] = {
        "morning": [
            "Good morning! Ready to make today amazing?",
            "Morning! I'm here and ready to help. What's on the agenda?",
            "Good morning! Hope you slept well. Let's get things done!",
        ],
        "afternoon": [
            "Good afternoon! How's your day going so far?",
            "Afternoon greetings! What can I help you with?",
            "Good afternoon! Hope your day is productive. Need assistance?",
        ],
        "evening": [
            "Good evening! Wind down time - anything I can help with?",
            "Evening! Hope you had a good day. What's on your mind?",
            "Good evening! Ready to wrap up the day or start something new?",
        ],
        "night": [
            "Good evening! Working late? I'm here to help.",
            "Night owl mode activated! What shall we work on?",
            "Hello! Burning the midnight oil? Let's make it productive.",
        ],
    }

    def __init__(
        self,
        user_name: str | None = None,
        special_dates: dict[tuple[int, int], str] | None = None,
    ) -> None:
        """Initialize the proactive greeter.

        Args:
            user_name: Optional user name for personalized greetings.
            special_dates: Optional custom special dates.
        """
        self._user_name = user_name
        self._special_dates = special_dates or self.SPECIAL_DATES

    def build_context(self, now: datetime.datetime | None = None) -> GreetingContext:
        """Build greeting context from current time.

        Args:
            now: Optional datetime to use (defaults to now).

        Returns:
            GreetingContext with current time information.
        """
        if now is None:
            now = datetime.datetime.now()

        return GreetingContext(
            hour=now.hour,
            day_of_week=now.weekday(),
            day_of_year=now.timetuple().tm_yday,
            is_weekend=now.weekday() >= 5,
            is_workday=now.weekday() < 5,
        )

    def _get_time_greeting(self, hour: int) -> tuple[str, str]:
        """Get time-based greeting.

        Args:
            hour: Current hour (0-23).

        Returns:
            Tuple of (time_period, greeting_message).
        """
        if 5 <= hour < 12:
            messages = self.TIME_GREETINGS["morning"]
            return "morning", self._pick_message(messages)
        elif 12 <= hour < 18:
            messages = self.TIME_GREETINGS["afternoon"]
            return "afternoon", self._pick_message(messages)
        elif 18 <= hour < 22:
            messages = self.TIME_GREETINGS["evening"]
            return "evening", self._pick_message(messages)
        else:
            messages = self.TIME_GREETINGS["night"]
            return "night", self._pick_message(messages)

    def _pick_message(self, messages: list[str]) -> str:
        """Pick a random message from the list.

        Args:
            messages: List of messages to choose from.

        Returns:
            Selected message.
        """
        import random

        return random.choice(messages)

    def _format_with_name(self, message: str, name: str | None) -> str:
        """Format message with user name if provided.

        Args:
            message: Base greeting message.
            name: Optional user name.

        Returns:
            Formatted message.
        """
        if name:
            # Insert name after the greeting
            parts = message.split("!", 1)
            if len(parts) == 2:
                return f"{parts[0]} {name}!{parts[1]}"
        return message

    def generate(
        self,
        context: GreetingContext | None = None,
        now: datetime.datetime | None = None,
    ) -> GreetingResult:
        """Generate a context-aware greeting.

        Args:
            context: Optional pre-built context.
            now: Optional datetime for time-based greetings.

        Returns:
            GreetingResult with message and metadata.
        """
        if context is None:
            if now is None:
                now = datetime.datetime.now()
            context = self.build_context(now)

        context_dict: dict[str, Any] = {
            "hour": context.hour,
            "day_of_week": context.day_of_week,
            "is_weekend": context.is_weekend,
            "user_name": self._user_name,
        }

        # Check for special dates first
        month_day = (now.month if now else datetime.datetime.now().month,
                     now.day if now else datetime.datetime.now().day)
        if month_day in self._special_dates:
            special_message = self._special_dates[month_day]
            return GreetingResult(
                message=self._format_with_name(special_message, self._user_name),
                greeting_type=GreetingType.SPECIAL,
                context_used=context_dict,
            )

        # Check for day-specific greetings
        if context.is_weekend:
            day_name = "Saturday" if context.day_of_week == 5 else "Sunday"
            time_period, time_msg = self._get_time_greeting(context.hour)
            messages = self.WEEKEND_MESSAGES
            base_message = self._pick_message(messages).format(
                time=time_period, day=day_name
            )
            return GreetingResult(
                message=self._format_with_name(base_message, self._user_name),
                greeting_type=GreetingType.WEEKEND,
                context_used=context_dict,
            )

        if context.day_of_week == 0:  # Monday
            base_message = self._pick_message(self.MONDAY_MESSAGES)
            return GreetingResult(
                message=self._format_with_name(base_message, self._user_name),
                greeting_type=GreetingType.MONDAY,
                context_used=context_dict,
            )

        if context.day_of_week == 4:  # Friday
            base_message = self._pick_message(self.FRIDAY_MESSAGES)
            return GreetingResult(
                message=self._format_with_name(base_message, self._user_name),
                greeting_type=GreetingType.FRIDAY,
                context_used=context_dict,
            )

        # Default to time-based greeting
        time_period, base_message = self._get_time_greeting(context.hour)
        greeting_type = GreetingType(time_period)

        return GreetingResult(
            message=self._format_with_name(base_message, self._user_name),
            greeting_type=greeting_type,
            context_used=context_dict,
        )

    def get_simple_greeting(self) -> str:
        """Get a simple time-aware greeting without context.

        Returns:
            Simple greeting string.
        """
        result = self.generate()
        return result.message


class GreetingManager:
    """Manage greeting state and history.

    Tracks:
    - Last greeting time
    - Greeting history
    - Cooldown period to avoid spam
    """

    # Don't greet more than once per hour
    DEFAULT_COOLDOWN_HOURS = 1.0

    def __init__(
        self,
        greeter: ProactiveGreeter | None = None,
        cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    ) -> None:
        """Initialize the greeting manager.

        Args:
            greeter: Optional ProactiveGreeter instance.
            cooldown_hours: Hours between greetings.
        """
        self._greeter = greeter or ProactiveGreeter()
        self._cooldown_hours = cooldown_hours
        self._last_greeting_time: datetime.datetime | None = None
        self._greeting_count: int = 0

    def should_greet(self, now: datetime.datetime | None = None) -> bool:
        """Check if we should greet now.

        Args:
            now: Optional datetime for checking.

        Returns:
            True if greeting is appropriate.
        """
        if now is None:
            now = datetime.datetime.now()

        # First time - always greet
        if self._last_greeting_time is None:
            return True

        # Check cooldown
        elapsed = (now - self._last_greeting_time).total_seconds() / 3600
        return elapsed >= self._cooldown_hours

    def generate_greeting(
        self,
        now: datetime.datetime | None = None,
        force: bool = False,
    ) -> str | None:
        """Generate a greeting if appropriate.

        Args:
            now: Optional datetime.
            force: Force generate even if in cooldown.

        Returns:
            Greeting message or None if in cooldown.
        """
        if now is None:
            now = datetime.datetime.now()

        if not force and not self.should_greet(now):
            return None

        greeting = self._greeter.generate(now=now)
        self._last_greeting_time = now
        self._greeting_count += 1

        logger.info(
            "greeting_generated",
            type=greeting.greeting_type.value,
            count=self._greeting_count,
        )

        return greeting.message

    @property
    def greeting_count(self) -> int:
        """Get total number of greetings generated."""
        return self._greeting_count

    @property
    def last_greeting_time(self) -> datetime.datetime | None:
        """Get the time of the last greeting."""
        return self._last_greeting_time
