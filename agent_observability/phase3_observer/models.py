from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from agent_observability.phase1_agent_host.models import ToolSchema
from agent_observability.phase2_tracing.models import ExecutionTraceSpan


class FailureCategory(str, Enum):
    MISSING_PARAMETERS = "MISSING_PARAMETERS"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    API_REJECTION = "API_REJECTION"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
    FORMAT_MISMATCH = "FORMAT_MISMATCH"


class EvaluationVerdict(BaseModel):
    """
    Result of evaluating an execution trace span against tool schemas and runtime expectations.
    """
    is_valid: bool = Field(..., description="Whether the execution was evaluated as successful and compliant")
    failure_category: Optional[FailureCategory] = Field(default=None, description="Classified category if failed")
    diagnostic_message: str = Field(default="", description="Detailed explanation of the failure or pass")
    deviations: List[str] = Field(default_factory=list, description="Specific schema or format deviations observed")
    span_id: str = Field(..., description="ID of the evaluated trace span")
    trace_id: str = Field(..., description="ID of the workflow trace")
    tool_name: Optional[str] = Field(default=None, description="Name of the tool evaluated, if applicable")
    tool_inputs: Dict[str, Any] = Field(default_factory=dict, description="Inputs supplied to the tool")
    tool_schema: Optional[ToolSchema] = Field(default=None, description="Reference tool schema used for evaluation")
