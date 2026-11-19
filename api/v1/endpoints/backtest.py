# -*- coding: utf-8 -*-
"""Backtest endpoints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_database_manager
from api.v1.schemas.backtest import (
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestResultItem,
    BacktestResultsResponse,
    PerformanceMetrics,
)
from api.v1.schemas.common import ErrorResponse
from src.services.backtest_service import BacktestService
from src.storage import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter()

BacktestAnalysisPhaseQuery = Literal["premarket", "intraday", "postmarket", "unknown"]


def _validate_analysis_date_range(
    analysis_date_from: Optional[date],
    analysis_date_to: Optional[date],
) -> None:
    if analysis_date_from and analysis_date_to and analysis_date_from > analysis_date_to:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_params",
                "message": "analysis_date_from cannot be after analysis_date_to",
            },
        )


@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        200: {"description": "การทดสอบกลับไปยังอดีตเสร็จสิ้นแล้ว"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="เริ่มต้นการทดสอบกลับไปยังอดีต",
    description="ประเมินการทดสอบกลับไปยังอดีตจากบันทึกวิเคราะห์อดีต และบันทึกผลลงใน backtest_results/backtest_summaries",
)
def run_backtest(
    request: BacktestRunRequest,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestRunResponse:
    try:
        _validate_analysis_date_range(request.analysis_date_from, request.analysis_date_to)
        service = BacktestService(db_manager)
        stats = service.run_backtest(
            code=request.code,
            force=request.force,
            eval_window_days=request.eval_window_days,
            min_age_days=request.min_age_days,
            analysis_date_from=request.analysis_date_from,
            analysis_date_to=request.analysis_date_to,
            limit=request.limit,
        )
        return BacktestRunResponse(**stats)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"การทดสอบกลับไปยังอดีตล้มเหลว: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"การทดสอบกลับไปยังอดีตล้มเหลว: {str(exc)}"},
        )


@router.get(
    "/results",
    response_model=BacktestResultsResponse,
    responses={
        200: {"description": "รายการผลลัพธ์การทดสอบกลับไปยังอดีต"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงผลลัพธ์การทดสอบกลับไปยังอดีต",
    description="ดึงผลลัพธ์การทดสอบกลับไปยังอดีตแบบแบ่งหน้า โดยรองรับการกรองตามรหัสหุ้น",
)
def get_backtest_results(
    code: Optional[str] = Query(None, description="กรองตามรหัสหุ้น"),
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="กรองตามช่วงเวลาประเมิน"),
    analysis_date_from: Optional[date] = Query(None, description="วันเริ่มต้นวันวิเคราะห์ (รวม)"),
    analysis_date_to: Optional[date] = Query(None, description="วันสิ้นสุดวันวิเคราะห์ (รวม)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="Filter by analysis phase: premarket/intraday/postmarket/unknown"),
    page: int = Query(1, ge=1, description="หน้าที่"),
    limit: int = Query(20, ge=1, le=200, description="จำนวนต่อหน้า"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> BacktestResultsResponse:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        data = service.get_recent_evaluations(
            code=code,
            eval_window_days=eval_window_days,
            limit=limit,
            page=page,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        items = [BacktestResultItem(**item) for item in data.get("items", [])]
        return BacktestResultsResponse(
            total=int(data.get("total", 0)),
            page=page,
            limit=limit,
            items=items,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"การสอบถามผลการทดสอบกลับไม่สำเร็จ: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"การสอบถามผลการทดสอบกลับไม่สำเร็จ: {str(exc)}"},
        )


@router.get(
    "/performance",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "ผลรวมของการทดสอบกลับ"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        404: {"description": "ไม่มีการสรุปผลการทดสอบกลับ", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงผลรวมของการทดสอบกลับ",
)
def get_overall_performance(
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="กรองตามช่วงเวลาประเมิน"),
    analysis_date_from: Optional[date] = Query(None, description="วันเริ่มต้นวันวิเคราะห์ (รวม)"),
    analysis_date_to: Optional[date] = Query(None, description="วันสิ้นสุดวันวิเคราะห์ (รวม)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="Filter by analysis phase: premarket/intraday/postmarket/unknown"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="overall",
            code=None,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "ไม่พบการสรุปผลการทดสอบกลับ"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"การสอบถามผลรวมการแสดงผลลัพธ์ล้มเหลว: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"การสอบถามผลรวมการแสดงผลลัพธ์ล้มเหลว: {str(exc)}"},
        )


@router.get(
    "/performance/{code}",
    response_model=PerformanceMetrics,
    responses={
        200: {"description": "ผลการทดสอบกลับของหุ้นแต่ละตัว"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        404: {"description": "ไม่มีการสรุปผลการทดสอบกลับ", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงผลการทดสอบกลับของหุ้นแต่ละตัว",
)
def get_stock_performance(
    code: str,
    eval_window_days: Optional[int] = Query(None, ge=1, le=120, description="กรองตามช่วงเวลาประเมิน"),
    analysis_date_from: Optional[date] = Query(None, description="วันเริ่มต้นวันวิเคราะห์ (รวม)"),
    analysis_date_to: Optional[date] = Query(None, description="วันสิ้นสุดวันวิเคราะห์ (รวม)"),
    analysis_phase: Optional[BacktestAnalysisPhaseQuery] = Query(None, description="Filter by analysis phase: premarket/intraday/postmarket/unknown"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> PerformanceMetrics:
    try:
        _validate_analysis_date_range(analysis_date_from, analysis_date_to)
        service = BacktestService(db_manager)
        summary = service.get_summary(
            scope="stock",
            code=code,
            eval_window_days=eval_window_days,
            analysis_date_from=analysis_date_from,
            analysis_date_to=analysis_date_to,
            analysis_phase=analysis_phase,
        )
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": f"ไม่พบการสรุปผลการทดสอบกลับของ {code}"},
            )
        return PerformanceMetrics(**summary)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_params", "message": str(exc)},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"การสอบถามผลการทดสอบกลับของหุ้นล้มเหลว: {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"การสอบถามผลการทดสอบกลับของหุ้นล้มเหลว: {str(exc)}"},
        )
