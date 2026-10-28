import json
import time
import uuid
import traceback
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SpanStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


class SpanType(str, Enum):
    PROMPT = "PROMPT"
    TOOL = "TOOL"
    AGENT_RUN = "AGENT_RUN"


class ErrorPayload(BaseModel):
    """Captures exact error details and complete stack trace."""
    error_type: str = Field(..., description="Exception class name")
    message: str = Field(..., description="Exception message")
    stack_trace: str = Field(..., description="Full formatted stack trace")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context or diagnostics")

    @classmethod
    def from_exception(cls, exc: Exception, details: Optional[Dict[str, Any]] = None) -> "ErrorPayload":
        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            stack_trace=traceback.format_exc(),
            details=details or {},
        )


class ExecutionTraceSpan(BaseModel):
    """
    Structured trace span recording the lifecycle of a prompt, tool call, or agent workflow.
    """
    trace_id: str = Field(default_factory=lambda: f"trace-{uuid.uuid4().hex[:12]}")
    span_id: str = Field(default_factory=lambda: f"span-{uuid.uuid4().hex[:8]}")
    parent_span_id: Optional[str] = Field(default=None)
    span_type: SpanType = Field(..., description="Type of operation being traced")
    name: str = Field(..., description="Name of the prompt, tool, or task")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Inputs provided to the operation")
    outputs: Optional[Any] = Field(default=None, description="Output generated on success")
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = Field(default=None)
    latency_ms: Optional[float] = Field(default=None, description="Execution duration in milliseconds")
    status: SpanStatus = Field(default=SpanStatus.PENDING)
    error: Optional[ErrorPayload] = Field(default=None, description="Exact error payload if failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata tags")

    def finish_success(self, outputs: Any) -> None:
        """Mark span as successfully completed with outputs and compute latency."""
        self.end_time = time.time()
        self.latency_ms = round((self.end_time - self.start_time) * 1000, 3)
        self.outputs = outputs
        self.status = SpanStatus.SUCCESS

    def finish_failure(self, exc: Exception, details: Optional[Dict[str, Any]] = None) -> None:
        """Mark span as failed, extract exact error payload and stack trace, and compute latency."""
        self.end_time = time.time()
        self.latency_ms = round((self.end_time - self.start_time) * 1000, 3)
        self.error = ErrorPayload.from_exception(exc, details)
        self.status = SpanStatus.FAILED

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Serialize span into structured JSON string."""
        return self.model_dump_json(indent=indent)
