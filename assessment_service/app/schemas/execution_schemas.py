"""
Pydantic schemas for Assessment Executions.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from enum import Enum

class AgentType(str, Enum):
    QWEN = "qwen"
    GEMINI_CLI = "gemini_cli"
    CLAUDE = "claude"

class SessionExecutionRequest(BaseModel):
    job_id: UUID = Field(..., description="The ID of the AssessmentJob to execute.")
    agent: AgentType = Field(AgentType.QWEN, description="The agent to dispatch for the assessment.")
    session_batch_size: Optional[int] = Field(5, description="The batch size for the assessment session.")
    chain_execution: Optional[bool] = Field(True, description="Whether to automatically start the next session when this one completes.")
    openai_base_url: Optional[str] = Field(None, description="OpenAI base URL, only for qwen agent.")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key, only for qwen agent.")
    openai_model: Optional[str] = Field(None, description="OpenAI model name, only for qwen agent.")

class SessionExecutionResponse(BaseModel):
    status: str = Field(..., description="The status of the dispatch (e.g., 'dispatched', 'error').")
    pid: Optional[int] = Field(None, description="The Process ID (PID) of the dispatched agent.")
    session_id: UUID = Field(..., description="The ID of the newly created session for this execution.")
    log_file_path: str = Field(..., description="The server-side path to the agent's log file.")
    command: str = Field(..., description="The exact command that was executed.")
    agent: AgentType = Field(..., description="The agent that was dispatched.")
    job_id: UUID = Field(..., description="The ID of the job being executed.")


class JobExecutionRequest(BaseModel):
    agent: AgentType = Field(AgentType.QWEN, description="The agent to dispatch for the assessment.")
    session_batch_size: Optional[int] = Field(5, description="The number of findings to process in each session.")
    openai_base_url: Optional[str] = Field(None, description="OpenAI base URL, only for qwen agent.")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key, only for qwen agent.")
    openai_model: Optional[str] = Field(None, description="OpenAI model name, only for qwen agent.")
    
    # Kosmos认证信息
    kosmos_username: Optional[str] = Field(None, description="Kosmos系统用户名")
    kosmos_password: Optional[str] = Field(None, description="Kosmos系统密码")
    
    # Agent提示词配置
    agent_prompt: Optional[str] = Field(None, description="自定义agent提示词，如果提供将覆盖默认提示词")


class JobExecutionResponse(BaseModel):
    status: str = Field(..., description="The status of the job dispatch (e.g., 'queued', 'error').")
    job_id: UUID = Field(..., description="The ID of the job being enqueued.")
    total_sessions_created: int = Field(..., description="The total number of sessions created and queued for the job.")
    message: str = Field(..., description="A confirmation message.")


class SessionStatus(str, Enum):
    """Session状态枚举"""
    READY_FOR_ASSESSMENT = "READY_FOR_ASSESSMENT"
    ASSESSING_CONTROLS = "ASSESSING_CONTROLS"
    SUBMITTED_FOR_REVIEW = "SUBMITTED_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABANDONED = "ABANDONED"


class RequeueSessionRequest(BaseModel):
    """重新调度session的请求schema"""
    target_states: List[SessionStatus] = Field(
        ..., 
        description="需要重新调度的session状态列表",
        example=["READY_FOR_ASSESSMENT", "ASSESSING_CONTROLS"]
    )
    session_batch_size: Optional[int] = Field(5, description="每个session批次的finding数量")
    agent: Optional[AgentType] = Field(AgentType.QWEN, description="使用的agent类型")
    openai_base_url: Optional[str] = Field(None, description="OpenAI base URL, only for qwen agent.")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key, only for qwen agent.")
    openai_model: Optional[str] = Field(None, description="OpenAI model name, only for qwen agent.")
    
    # Kosmos认证信息
    kosmos_username: Optional[str] = Field(None, description="Kosmos系统用户名")
    kosmos_password: Optional[str] = Field(None, description="Kosmos系统密码")
    
    # Agent提示词配置
    agent_prompt: Optional[str] = Field(None, description="自定义agent提示词，如果提供将覆盖默认提示词")
    
    class Config:
        use_enum_values = True


class RequeueSessionResponse(BaseModel):
    """重新调度session的响应schema"""
    status: str = Field(..., description="重新调度状态 (e.g., 'success', 'partial', 'no_action')")
    job_id: UUID = Field(..., description="job ID")
    total_sessions_processed: int = Field(..., description="处理的session总数")
    sessions_requeued: int = Field(..., description="重新入队的session数量")
    sessions_skipped: int = Field(..., description="跳过的session数量")
    state_breakdown: dict = Field(..., description="各状态session的详细统计")
    target_states: List[str] = Field(..., description="目标状态列表")
    message: str = Field(..., description="详细的操作说明")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "total_sessions_processed": 10,
                "sessions_requeued": 7,
                "sessions_skipped": 3,
                "state_breakdown": {
                    "READY_FOR_ASSESSMENT": {"total": 3, "requeued": 3, "skipped": 0},
                    "ASSESSING_CONTROLS": {"total": 4, "requeued": 4, "skipped": 0},
                    "SUBMITTED_FOR_REVIEW": {"total": 1, "requeued": 0, "skipped": 1},
                    "COMPLETED": {"total": 1, "requeued": 0, "skipped": 1},
                    "FAILED": {"total": 1, "requeued": 0, "skipped": 1},
                    "ABANDONED": {"total": 0, "requeued": 0, "skipped": 0}
                },
                "target_states": ["READY_FOR_ASSESSMENT", "ASSESSING_CONTROLS"]
            }
        }
    }
