from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecoveryStrategyType(str, Enum):
    CORRECT_PARAMETERS = "CORRECT_PARAMETERS"
    COERCE_TYPES = "COERCE_TYPES"
    HYDRATE_SYNTAX = "HYDRATE_SYNTAX"
    RETRY_WITH_FALLBACK = "RETRY_WITH_FALLBACK"
    FAIL_GRACEFUL = "FAIL_GRACEFUL"


class CriticDiagnosis(BaseModel):
    """
    Diagnostic analysis produced by the secondary Critic function,
    pinpointing root cause and generating corrected parameters for context injection.
    """
    root_cause: str = Field(..., description="Detailed explanation of the failure's root cause")
    strategy: RecoveryStrategyType = Field(..., description="Chosen self-healing strategy")
    corrected_inputs: Dict[str, Any] = Field(default_factory=dict, description="Repaired parameters ready for re-execution")
    explanation: str = Field(default="", description="Human-readable remediation guidance")
    context_injection: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured context injected back into primary agent/tool runtime"
    )
    confidence: float = Field(default=1.0, description="Confidence in this diagnosis [0.0 - 1.0]")


class RecoveryResult(BaseModel):
    """Result of the automated self-recovery attempt."""
    success: bool
    original_span_id: str
    trace_id: str
    tool_name: str
    retry_count: int
    diagnosis: CriticDiagnosis
    recovered_output: Optional[Any] = None
    error_message: Optional[str] = None
