from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class DatasetBuildItem(BaseModel):
    type: Literal["jec", "cail"]
    splits: list[str] = Field(default_factory=list)
    max_items: Optional[int] = None  # JEC: per combined load; CAIL: per split max cases


class DatasetBuildRequest(BaseModel):
    rebuild: bool = False
    datasets: list[DatasetBuildItem] = Field(default_factory=list)


class DatasetBuildJobCreate(BaseModel):
    job_id: str


class DatasetBuildJobStatus(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    logs: list[str] = Field(default_factory=list)
    total_written: int = 0
    error: Optional[str] = None
