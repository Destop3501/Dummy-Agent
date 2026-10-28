from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Specification for an individual parameter accepted by a tool."""
    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Expected data type, e.g. string, integer, float, boolean, object, array")
    description: Optional[str] = Field(default="", description="Description of the parameter")
    required: bool = Field(default=True, description="Whether this parameter must be supplied")
    default: Optional[Any] = Field(default=None, description="Default value if not supplied")


class ToolSchema(BaseModel):
    """Schema definition for an external customer agent's tool."""
    name: str = Field(..., description="Unique tool name")
    description: str = Field(default="", description="Tool purpose and behavior description")
    parameters: List[ToolParameter] = Field(default_factory=list, description="List of expected parameters")
    expected_output_type: Optional[str] = Field(
        default="object",
        description="Expected return format type, e.g., string, integer, dict, list"
    )

    def get_parameter(self, param_name: str) -> Optional[ToolParameter]:
        """Look up a parameter by name."""
        for param in self.parameters:
            if param.name == param_name:
                return param
        return None

    def get_required_param_names(self) -> List[str]:
        """Return names of all required parameters."""
        return [p.name for p in self.parameters if p.required]


class AgentHostMetadata(BaseModel):
    """Metadata describing the registered customer agent."""
    agent_id: str
    name: str
    version: str = "1.0.0"
    description: Optional[str] = None


@runtime_checkable
class CustomerAgentProtocol(Protocol):
    """
    Duck-typing protocol for external customer AI agents.
    Customer agents need only provide an entry point (e.g. run, execute, or invoke)
    and optional tool-calling capabilities. No internal model modification is required.
    """
    def run(self, prompt: str, **kwargs: Any) -> Any:
        ...
