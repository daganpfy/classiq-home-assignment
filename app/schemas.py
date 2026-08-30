from __future__ import annotations

from pydantic import BaseModel, Field


class SubmitTaskRequest(BaseModel):
    qc: str = Field(..., min_length=1, description="Serialized QASM3 quantum circuit.")


class SubmitTaskResponse(BaseModel):
    task_id: str
    message: str
