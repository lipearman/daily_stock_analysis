# -*- coding: utf-8 -*-
"""
===================================
分析相关模型
===================================

职责：
1. 定义分析请求和响应模型
2. 定义任务状态模型
3. 定义异步任务队列相关模型
"""

from typing import Optional, List, Any, Literal
from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN
from src.utils.market_review_region import normalize_market_review_region_strict


class TaskStatusEnum(str, Enum):
    """รายการสถานะงาน"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


AnalysisPhase = Literal["auto", "premarket", "intraday", "postmarket"]


class AnalyzeRequest(BaseModel):
    """Analysis request parameters"""
    
    stock_code: Optional[str] = Field(
        None, 
        description="รหัสหุ้นเดี่ยว", 
        json_schema_extra={"example": "600519"},
    )
    stock_codes: Optional[List[str]] = Field(
        None, 
        description="รหัสหุ้นหลายตัว (เลือกได้กับ stock_code)",
        json_schema_extra={"example": ["600519", "000858"]},
    )
    report_type: str = Field(
        "detailed",
        description="report type: simple (concise) / detailed (full) / full (full) / brief (concise)",
        pattern="^(simple|detailed|full|brief)$",
    )
    force_refresh: bool = Field(
        False,
        description="force refresh (ignore cache)"
    )
    async_mode: bool = Field(
        False,
        description="use asynchronous mode"
    )
    analysis_phase: AnalysisPhase = Field(
        "auto",
        description="analysis phase coverage: auto (auto-infer) / premarket (pre-market) / intraday (intraday) / postmarket (post-market)",
    )
    stock_name: Optional[str] = Field(
        None,
        description="stock name selected by user (provided during autocomplete)",
        json_schema_extra={"example": "Guizhou Maotai"},
    )
    original_query: Optional[str] = Field(
        None,
        description="original user input (e.g., Maotai, gzmt, 600519)",
        json_schema_extra={"example": "Maotai"},
    )
    selection_source: Optional[str] = Field(
        None,
        description="stock selection source: manual (manual input) | autocomplete (auto-complete) | import (import) | image (image recognition)",
        pattern=SELECTION_SOURCE_PATTERN,
        json_schema_extra={"example": "autocomplete"},
    )
    notify: bool = Field(
        True,
        description="send push notification (Telegram / enterprise WeChat, etc.)"
    )
    report_language: Optional[Literal["zh", "en", "ko"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="output language for this analysis report; defaults to global REPORT_LANGUAGE if not provided",
    )
    skills: Optional[List[str]] = Field(
        None,
        validation_alias=AliasChoices("skills", "strategies"),
        description="list of strategy skill IDs used for this analysis; compatible with legacy strategies field",
        json_schema_extra={"example": ["bull_trend", "growth_quality"]},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "report_type": "detailed",
            "force_refresh": False,
            "async_mode": False,
            "analysis_phase": "auto",
            "stock_name": "Guizhou Maotai",
            "original_query": "Maotai",
            "selection_source": "autocomplete",
            "notify": True,
            "report_language": "zh",
            "skills": ["bull_trend"]
        }
    })


class MarketReviewRequest(BaseModel):
    """Market review trigger parameters."""

    send_notification: bool = Field(
        True,
        description="send push notification after market review completion",
    )
    report_language: Optional[Literal["zh", "en", "ko"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="output language for this market review report; defaults to global REPORT_LANGUAGE if not provided",
    )
    region: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description=(
            "market coverage for this market review. Valid tokens are cn, hk, us, jp, kr, tw, both;"
            "both ใช้เดี่ยว ๆ เท่านั้น token อื่นรวมกันด้วยจุลภาคได้ ระบบจะละเว้นตัวพิมพ์และช่องว่างสองข้าง token"
            "ตัดซ้ำและเรียงตาม cn,hk,us,jp,kr,tw ค่าว่าง token ว่าง token ไม่รู้จัก การใช้ both ปนกัน หรือเกิน"
            "64 ตัวอักษร จะตอบ 4xx ทั้งชุด ไม่รันบางส่วน หากไม่ส่งจะใช้ MARKET_REVIEW_REGION ระดับระบบ"
        ),
        json_schema_extra={
            "example": "cn,us",
            "examples": ["cn", "tw", "cn,tw", "both"],
        },
    )

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: Optional[str]) -> Optional[str]:
        """Strictly validate request input and return its canonical ordering."""
        if value is None:
            return None
        return normalize_market_review_region_strict(value)


class MarketReviewAccepted(BaseModel):
    """Market review background task accepted response."""

    status: str = Field("accepted", description="สถานะการส่งงาน")
    message: str = Field(..., description="ข้อความแจ้ง")
    send_notification: bool = Field(..., description="ส่งการแจ้งเตือนหรือไม่")
    region: str = Field(
        ...,
        description="ขอบเขตตลาด canonical ที่งานนี้รันจริง",
        examples=["us", "jp,kr"],
    )
    trace_id: Optional[str] = Field(
        None,
        description="trace ID สำหรับวินิจฉัยของงานเบื้องหลังนี้",
    )
    task_id: Optional[str] = Field(
        None,
        description="ID ของงาน (ส่งกลับเฉพาะเมื่อส่งงานสำเร็จจริง)",
    )


class AnalysisResultResponse(BaseModel):
    """Analysis Result Response Model"""
    
    query_id: str = Field(..., description="Unique identifier for analysis record")
    trace_id: Optional[str] = Field(None, description="Diagnostic trace ID")
    stock_code: str = Field(..., description="Stock code")
    stock_name: Optional[str] = Field(None, description="Stock name")
    report: Optional[Any] = Field(None, description="Analysis report")
    diagnostic_summary: Optional[Any] = Field(None, description="สรุปการวินิจฉัยการรัน")
    created_at: str = Field(..., description="Creation time")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query_id": "abc123def456",
            "stock_code": "600519",
            "stock_name": "Guizhou Maotai",
            "report": {
                "summary": {
                    "sentiment_score": 75,
                    "operation_advice": "Holding"
                }
            },
            "created_at": "2024-01-01T12:00:00"
        }
    })


class TaskAccepted(BaseModel):
    """Async task acceptance response"""
    
    task_id: str = Field(..., description="Task ID, used to query status")
    trace_id: Optional[str] = Field(None, description="Diagnostic trace ID")
    status: str = Field(
        ..., 
        description="สถานะงาน",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="ข้อความแจ้ง")
    analysis_phase: AnalysisPhase = Field("auto", description="Requested analysis phase")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "pending",
            "message": "Analysis task accepted",
            "analysis_phase": "auto"
        }
    })


class BatchTaskAcceptedItem(BaseModel):
    """Single successfully submitted item in batch async task."""

    task_id: str = Field(..., description="Task ID, used to query status")
    trace_id: Optional[str] = Field(None, description="Diagnostic trace ID")
    stock_code: str = Field(..., description="Stock code")
    status: str = Field(
        ...,
        description="สถานะงาน",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="ข้อความแจ้ง")
    analysis_phase: AnalysisPhase = Field("auto", description="Requested analysis phase")
    asset_type: Optional[Literal["stock", "index"]] = Field(
        None,
        description="Optional asset type (stock/index) from parser source; passed through by submitted analysis_target, optional for legacy clients",
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "stock_code": "600519",
            "status": "pending",
            "message": "Analysis task has been added to queue: 600519",
            "analysis_phase": "auto"
        }
    })


class BatchDuplicateTaskItem(BaseModel):
    """Duplicate submission item in batch async task."""

    stock_code: str = Field(..., description="Stock code")
    existing_task_id: str = Field(..., description="Existing task ID")
    message: str = Field(..., description="Error message")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "existing_task_id": "task_existing_123",
            "message": "Stock 600519 is being analyzed (task_id: task_existing_123)"
        }
    })


class RejectedTaskItem(BaseModel):
    """Single target item explicitly rejected in batch async task (e.g., unregistered CSI index)."""

    stock_code: str = Field(..., description="Rejected target code")
    message: str = Field(..., description="Reason for rejection")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "930956.CSI",
            "message": "unregistered CSI index: '930956.CSI' is not in the index registry",
        }
    })


class BatchTaskAcceptedResponse(BaseModel):
    """Batch async task acceptance response."""

    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="List of successfully submitted tasks")
    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="List of duplicate and skipped tasks")
    rejected: Optional[List[RejectedTaskItem]] = Field(
        None,
        description="List of explicitly rejected targets in batch (e.g., unregistered CSI index), returned only in async batch requests",
    )
    message: str = Field(..., description="Summary information")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "accepted": [
                {
                    "task_id": "task_abc123",
                    "stock_code": "600519",
                    "status": "pending",
                    "message": "Analysis task has been added to queue: 600519",
                    "analysis_phase": "auto"
                }
            ],
            "duplicates": [
                {
                    "stock_code": "000858",
                    "existing_task_id": "task_existing_456",
                    "message": "Stock 000858 is being analyzed (task_id: task_existing_456)"
                }
            ],
            "message": "Submitted 1 task, 1 duplicate skipped"
        }
    })


class TaskStatus(BaseModel):
    """Task status model"""
    
    task_id: str = Field(..., description="Task ID")
    trace_id: Optional[str] = Field(None, description="Diagnostic trace ID")
    status: TaskStatusEnum = Field(
        ..., 
        description="สถานะงาน",
    )
    progress: Optional[int] = Field(
        None, 
        description="Progress percentage (0-100)",
        ge=0,
        le=100
    )
    result: Optional[AnalysisResultResponse] = Field(
        None, 
        description="Analysis result (exists only when completed)"
    )
    market_review_report: Optional[str] = Field(
        None,
        description="Report text returned by index review task (only for index review tasks)",
    )
    market_review_payload: Optional[Any] = Field(
        None,
        description="Structured market-review payload for API/Web consumers.",
    )
    region: Optional[str] = Field(
        None,
        description="Actual canonical market scope executed by index review task",
    )
    error: Optional[str] = Field(
        None, 
        description="Error message (exists only when failed)"
    )
    stock_name: Optional[str] = Field(None, description="Stock name")
    original_query: Optional[str] = Field(None, description="User's original input")
    selection_source: Optional[str] = Field(
        None,
        description="Source selection",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: Optional[AnalysisPhase] = Field(
        None,
        description="Requested analysis phase; historical DB fallback with no persistent field may be empty",
    )
    skills: Optional[List[str]] = Field(None, description="List of strategy skill IDs used in this task")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "completed",
            "progress": 100,
            "result": None,
            "market_review_report": None,
            "error": None,
            "stock_name": "Guizhou Maotai",
            "original_query": "Maotai",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskInfo(BaseModel):
    """
    Task details model

    Used for task list and SSE event delivery
    """
    
    task_id: str = Field(..., description="Task ID")
    trace_id: Optional[str] = Field(None, description="Diagnostic trace ID")
    stock_code: str = Field(..., description="Stock code")
    stock_name: Optional[str] = Field(None, description="Stock name")
    status: TaskStatusEnum = Field(..., description="สถานะงาน")
    progress: int = Field(0, description="Progress percentage (0-100)", ge=0, le=100)
    message: Optional[str] = Field(None, description="Status message")
    report_type: str = Field("detailed", description="Report type")
    created_at: str = Field(..., description="Creation time")
    started_at: Optional[str] = Field(None, description="Start execution time")
    completed_at: Optional[str] = Field(None, description="Completion time")
    error: Optional[str] = Field(None, description="Error message (exists only when failed)")
    original_query: Optional[str] = Field(None, description="User's original input")
    selection_source: Optional[str] = Field(
        None,
        description="Source selection",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: AnalysisPhase = Field("auto", description="Requested analysis phase")
    skills: Optional[List[str]] = Field(None, description="List of strategy skill IDs used in this task")
    region: Optional[str] = Field(
        None,
        description="Actual canonical market scope executed by index review task",
    )
    asset_type: Optional[Literal["stock", "index"]] = Field(
        None,
        description="Optional asset type (stock/index) from parser source; passed through by submitted analysis_target, optional for legacy clients",
    )
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "abc123def456",
            "stock_code": "600519",
            "stock_name": "Guizhou Maotai",
            "status": "processing",
            "progress": 50,
            "message": "Processing...",
            "report_type": "detailed",
            "created_at": "2026-02-05T10:30:00",
            "started_at": "2026-02-05T10:30:01",
            "completed_at": None,
            "error": None,
            "original_query": "Maotai",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskListResponse(BaseModel):
    """Task list response model"""
    
    total: int = Field(..., description="Total tasks")
    pending: int = Field(..., description="Number of pending tasks")
    processing: int = Field(..., description="Number of processing tasks")
    tasks: List[TaskInfo] = Field(..., description="Task List")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 3,
            "pending": 1,
            "processing": 2,
            "tasks": []
        }
    })


class DuplicateTaskErrorResponse(BaseModel):
    """Duplicate task error response model"""
    
    error: str = Field("duplicate_task", description="Error type")
    message: str = Field(..., description="Error message")
    stock_code: str = Field(..., description="Stock code")
    existing_task_id: str = Field(..., description="Existing task ID")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "duplicate_task",
            "message": "Stock 600519 is being analyzed",
            "stock_code": "600519",
            "existing_task_id": "abc123def456"
        }
    })
