from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

ToolName = Literal["scheme_retrieval","eligibility_check","apply_scheme"]

class ToolCall(BaseModel):
    tool: ToolName
    input: Dict[str, Any] = Field(default_factory=dict)

class AgentPlan(BaseModel):
    next_state: Literal["RUN_TOOLS","ASK_MISSING","RESPOND"] = "RESPOND"
    assistant_message_mr: str = ""
    questions_mr: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    ui_intent: Literal["chat","question","error"] = "chat"
    scheme_id: Optional[str] = None
