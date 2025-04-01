from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class SalesReportRequest(BaseModel):
    start_date: str
    end_date: str

class AgentLogEntry(BaseModel):
    timestamp: datetime
    agent_name: str
    activity_type: str
    details: Optional[str]
    context_data: Optional[Dict[str, Any]]

class AgentLogResponse(BaseModel):
    logs: List[AgentLogEntry]
    total: int
    page: int
    page_size: int

class AgentLogFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    agent_name: Optional[str] = None
    activity_type: Optional[str] = None
    page: int = 1
    page_size: int = 50
