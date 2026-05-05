"""
Abstract base class for all agents in the multi-agent system.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import time

from .message_bus import AgentMessage, MessageBus


class BaseAgent(ABC):
    """
    Base class for all specialized agents.
    Handles registration with the message bus and provides common utilities.
    """

    def __init__(self, name: str, bus: MessageBus):
        self.name = name
        self.bus = bus
        self.bus.register(name, self._wrapped_handle)
        self._call_count = 0
        self._total_time_ms = 0.0
        self._logs: list = []

    def _wrapped_handle(self, message: AgentMessage) -> AgentMessage:
        """Wraps handle_message with timing and logging."""
        start = time.time()
        self._call_count += 1
        self.log(f"Processing {message.type.value} from {message.sender}")

        try:
            response = self.handle_message(message)
            elapsed_ms = (time.time() - start) * 1000
            self._total_time_ms += elapsed_ms
            if response:
                response.duration_ms = elapsed_ms
                self.log(f"Completed in {elapsed_ms:.1f}ms")
            return response
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            self.log(f"ERROR: {e} (after {elapsed_ms:.1f}ms)")
            raise

    @abstractmethod
    def handle_message(self, message: AgentMessage) -> AgentMessage:
        """Process incoming message and return response."""
        pass

    def log(self, msg: str):
        """Log a message with agent name prefix."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] [{self.name}] {msg}"
        print(entry)
        self._logs.append(entry)
        if len(self._logs) > 50:
            self._logs.pop(0)

    def get_stats(self) -> dict:
        """Return agent performance stats."""
        return {
            "name": self.name,
            "calls": self._call_count,
            "total_time_ms": round(self._total_time_ms, 2),
            "avg_time_ms": round(self._total_time_ms / max(self._call_count, 1), 2)
        }
