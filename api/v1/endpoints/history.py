# -*- coding: utf-8 -*-
"""
===================================
历史记录接口
===================================

职责：
1. 提供 GET /api/v1/history 历史列表查询接口
2. 提供 GET /api/v1/history/{query_id} 历史详情查询接口
"""

import logging
from typing import Any, Mapping, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Body
from fastapi.responses import HTMLResponse, Response

from api.deps import get_database_manager
from api.v1.schemas.history import (
    HistoryListResponse,
    HistoryItem,
    DeleteHistoryRequest,
    DeleteHistoryResponse,
    NewsIntelItem,
    NewsIntelResponse,
    AnalysisReport,
    ReportMeta,
    ReportSummary,
    ReportStrategy,
    ReportDetails,
    MarkdownReportResponse,
    RunDiagnosticSummaryResponse,
    StockBarItem,
    StockBarResponse,
)
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.run_flow import RunFlowSnapshot
from src.storage import DatabaseManager
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.services.history_service import HistoryService, MarkdownReportGenerationError
from src.services.analysis_service import asset_type_from_canonical_code
from src.schemas.decision_action import build_action_fields
from src.utils.data_processing import (
    normalize_model_used,
    extract_fundamental_detail_fields,
    extract_board_detail_fields,
    extract_market_structure_detail_field,
    extract_realtime_detail_fields,
)
from src.analysis_context_pack_overview import (
    extract_analysis_context_pack_overview,
    sanitize_context_snapshot_for_api,
)
from src.market_phase_summary import extract_market_phase_summary
from src.config import get_config
from src.md2img import markdown_to_image
from src.share_image import (
    ShareImageBranding,
    build_share_image_html,
    share_image_branding_from_config,
)

logger = logging.getLogger(__name__)

router = APIRouter()
_DELETE_BY_CODE_BATCH_SIZE = 10_000


def _history_share_image_payload(result: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """Return the exact persisted payload used by the deterministic poster."""

    if result.get("report_type") == "market_review":
        context_snapshot = result.get("context_snapshot")
        if isinstance(context_snapshot, Mapping):
            market_payload = context_snapshot.get("market_review_payload")
            if isinstance(market_payload, Mapping):
                return market_payload

    raw_result = result.get("raw_result")
    return raw_result if isinstance(raw_result, Mapping) else None


def _history_share_image_input(
    record_id: str,
    db_manager: DatabaseManager,
) -> tuple[Mapping[str, Any], str]:
    """Load the shared persisted input used by PNG and desktop HTML renderers."""

    service = HistoryService(db_manager)
    result = service.resolve_and_get_detail(record_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"ไม่พบบันทึกการวิเคราะห์ที่มี id/query_id={record_id}",
            },
        )

    try:
        markdown_content = service.get_markdown_report(record_id)
    except MarkdownReportGenerationError as exc:
        logger.error("Share image report generation failed for %s: %s", record_id, exc.message)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": f"การสร้างภาพสำหรับแชร์ล้มเหลว: {exc.message}",
            },
        ) from exc

    if not markdown_content:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"ไม่พบเนื้อหาของรายงานที่มี id/query_id={record_id}",
            },
        )
    return result, markdown_content


def _history_share_image_branding(config: object) -> ShareImageBranding:
    return share_image_branding_from_config(config)


def _stock_bar_group_key(record_code: str, display_code: str) -> str:
    """Build the stock-bar grouping key from the *persisted* code.

    PR #2312: registered indices are typed by the persisted ``record.code``
    (never guessed from the display code) and group by the parser canonical
    (lowercase ``sh000016`` / ``csi930955``), so every explicit index form
    (uppercase legacy / dotted alias) converges to one row and never folds
    with the bare same-code stock. Stocks keep the legacy display-based
    normalization (``SH600519``/``600519.SH`` -> ``600519``, JP/KR legacy bare
    ``005930`` merging with ``005930.KS`` etc.), preserving existing semantics.
    """
    from data_provider.base import normalize_stock_code
    from src.services.stock_list_parser import ParseStatus, parse_analysis_target

    code = str(record_code or "").strip()
    if not code:
        return normalize_stock_code(display_code or "")
    try:
        target = parse_analysis_target(code)
    except Exception:
        return normalize_stock_code(display_code or "")
    if target.asset_type == ParseStatus.INDEX:
        return target.canonical_id
    return normalize_stock_code(display_code or "")


def _raw_result_value(raw_result: Any, key: str) -> Any:
    if not isinstance(raw_result, dict):
        return None

    value = raw_result.get(key)
    if value is not None and value != "":
        return value

    for container_key in ("summary", "dashboard"):
        container = raw_result.get(container_key)
        if isinstance(container, dict):
            nested_value = container.get(key)
            if nested_value is not None and nested_value != "":
                return nested_value

    return None


def _coalesce_text(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _coalesce_int(*values: Any) -> Optional[int]:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


def _extract_guardrail_reason(raw_result: Any) -> Optional[str]:
    if not isinstance(raw_result, dict):
        return None
    for reason in (
        raw_result.get("guardrail_reason"),
        raw_result.get("downgrade_reason"),
        raw_result.get("decision_score_guardrail_reason"),
    ):
        if reason is not None:
            text = str(reason).strip()
            if text:
                return text

    metadata = raw_result.get("metadata")
    if isinstance(metadata, dict):
        metadata_reason = metadata.get("guardrail_reason") or metadata.get("downgrade_reason")
        if metadata_reason is not None:
            text = str(metadata_reason).strip()
            if text:
                return text
    return None


@router.get(
    "",
    response_model=HistoryListResponse,
    responses={
        200: {"description": "รายการบันทึกประวัติ"},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงรายการบันทึกการวิเคราะห์ประวัติ",
    description="Paginated retrieval of historical analysis summaries, filterable by stock code and date range"
)
def get_history_list(
    stock_code: Optional[str] = Query(None, description="กรองตามรหัสหุ้น"),
    report_type: Optional[str] = Query(None, description="Filter by report type, e.g., market_review"),
    start_date: Optional[str] = Query(None, description="Start Date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End Date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(20, ge=1, le=100, description="จำนวนต่อหน้า"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> HistoryListResponse:
    """
    获取历史分析列表
    
    分页获取历史分析记录摘要，支持按股票代码和日期范围筛选
    
    Args:
        stock_code: 股票代码筛选
        report_type: 报告类型筛选
        start_date: 开始日期
        end_date: 结束日期
        page: 页码
        limit: 每页数量
        db_manager: 数据库管理器依赖
        
    Returns:
        HistoryListResponse: 历史记录列表
    """
    try:
        service = HistoryService(db_manager)
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_history_list(
            stock_code=stock_code,
            report_type=report_type,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit
        )
        
        # 转换为响应模型
        items = [
            HistoryItem(
                id=item.get("id"),
                query_id=item.get("query_id", ""),
                stock_code=item.get("stock_code", ""),
                stock_name=item.get("stock_name"),
                report_type=item.get("report_type"),
                region=item.get("region"),
                trend_prediction=item.get("trend_prediction"),
                analysis_summary=item.get("analysis_summary"),
                sentiment_score=item.get("sentiment_score"),
                operation_advice=item.get("operation_advice"),
                action=item.get("action"),
                action_label=item.get("action_label"),
                current_price=item.get("current_price"),
                change_pct=item.get("change_pct"),
                volume_ratio=item.get("volume_ratio"),
                turnover_rate=item.get("turnover_rate"),
                model_used=item.get("model_used"),
                created_at=item.get("created_at"),
                market_phase_summary=item.get("market_phase_summary"),
                asset_type=item.get("asset_type"),
            )
            for item in result.get("items", [])
        ]
        
        return HistoryListResponse(
            total=result.get("total", 0),
            page=page,
            limit=limit,
            items=items
        )
        
    except Exception as e:
        logger.error(f"Failed to query history list: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Query history list failed: {str(e)}"
            }
        )


@router.delete(
    "/by-code/{stock_code}",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "Deletion successful"},
        400: {"description": "Stock code cannot be empty", "model": ErrorResponse},
        404: {"description": "No record found", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="Delete historical analysis records by stock code",
    description="Delete all historical analysis records for a specified stock code (supports variant normalization matching)",
)
def delete_history_by_code(
    stock_code: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> DeleteHistoryResponse:
    try:
        candidates = HistoryService._history_code_filter_candidates(stock_code)
        if not candidates:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_request", "message": "stock_code cannot be empty"},
            )

        deleted = 0
        while True:
            records, _ = db_manager.get_analysis_history_paginated(
                code=candidates,
                limit=_DELETE_BY_CODE_BATCH_SIZE,
            )
            record_ids = [r.id for r in records if r.id is not None]
            if not record_ids:
                break

            batch_deleted = db_manager.delete_analysis_history_records(record_ids)
            if batch_deleted == 0:
                raise RuntimeError("history deletion made no progress")
            deleted += batch_deleted

            if len(records) < _DELETE_BY_CODE_BATCH_SIZE:
                break

        return DeleteHistoryResponse(deleted=deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete historical records by stock code: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"Deletion failed: {str(e)}"},
        )


@router.delete(
    "",
    response_model=DeleteHistoryResponse,
    responses={
        200: {"description": "Deletion successful"},
        400: {"description": "Invalid request parameters", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="Delete historical analysis records",
    description="Delete historical analysis records by primary key ID"
)
def delete_history_records(
    request: DeleteHistoryRequest = Body(...),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> DeleteHistoryResponse:
    """
    按主键 ID 批量删除历史分析记录。
    """
    record_ids = sorted({record_id for record_id in request.record_ids if record_id is not None})
    if not record_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "message": "record_ids cannot be empty"
            }
        )

    try:
        service = HistoryService(db_manager)
        deleted = service.delete_history_records(record_ids)
        return DeleteHistoryResponse(deleted=deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete historical records: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Failed to delete historical records: {str(e)}"
            }
        )


@router.get(
    "/stocks",
    response_model=StockBarResponse,
    responses={
        200: {"description": "List of unique individual stocks"},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงรายการหุ้นที่ไม่ซ้ำ",
    description="ส่งข้อมูลสรุปการวิเคราะห์ล่าสุดของแต่ละหุ้นจากประวัติ ไม่รวมรีวิวตลาด (code=MARKET)",
)
def get_stock_bar(
    start_date: Optional[str] = Query(None, description="Start Date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End Date (YYYY-MM-DD)"),
    limit: int = Query(200, ge=1, le=500, description="จำนวนสูงสุดที่ส่งกลับ"),
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> StockBarResponse:
    try:
        from datetime import date as date_type
        from src.utils.data_processing import parse_json_field

        service = HistoryService(db_manager)
        start = date_type.fromisoformat(start_date) if start_date else None
        end = date_type.fromisoformat(end_date) if end_date else None

        # Fetch more than limit to compensate for normalization dedup shrinkage
        # (e.g. 002460 + 002460.SZ both initially counted but merged to one)
        fetch_limit = min(limit * 3, 500)
        records = db_manager.get_distinct_stocks_from_history(
            start_date=start,
            end_date=end,
            limit=fetch_limit,
        )

        # Deduplicate by normalized code, keeping the record with highest id
        seen: dict = {}
        for record in records:
            display_code = service._display_stock_code(record.code or "")
            norm_code = _stock_bar_group_key(record.code or "", display_code)
            if norm_code not in seen or record.id > seen[norm_code].id:
                seen[norm_code] = record

        items = []
        for norm_code in seen:
            record = seen[norm_code]
            raw_result = parse_json_field(getattr(record, "raw_result", None))
            model_used = raw_result.get("model_used") if isinstance(raw_result, dict) else None
            sentiment_score = _coalesce_int(
                record.sentiment_score,
                _raw_result_value(raw_result, "sentiment_score"),
            )
            operation_advice = _coalesce_text(
                record.operation_advice,
                _raw_result_value(raw_result, "operation_advice"),
            )
            action_fields = build_action_fields(
                operation_advice=operation_advice,
                explicit_action=_raw_result_value(raw_result, "action"),
                report_type=record.report_type,
                report_language=normalize_report_language(
                    _raw_result_value(raw_result, "report_language")
                ),
                sentiment_score=sentiment_score,
                guardrail_reason=_extract_guardrail_reason(raw_result),
                align_with_score=True,
            )

            display_stock_code = service._display_stock_code(record.code)
            analysis_count = db_manager.get_analysis_history_paginated(
                code=HistoryService._history_code_filter_candidates(display_stock_code),
                limit=1,
            )[1]
            items.append(
                StockBarItem(
                    id=record.id,
                    stock_code=display_stock_code,
                    stock_name=record.name,
                    report_type=record.report_type,
                    sentiment_score=sentiment_score,
                    operation_advice=operation_advice,
                    action=action_fields["action"],
                    action_label=action_fields["action_label"],
                    analysis_count=analysis_count,
                    last_analysis_time=service._serialize_created_at(record.created_at),
                    model_used=normalize_model_used(model_used),
                    market_phase_summary=service._display_market_phase_summary(
                        record.code,
                        getattr(record, "context_snapshot", None),
                    ),
                    asset_type=asset_type_from_canonical_code(record.code),
                )
            )

        items = items[:limit]
        return StockBarResponse(total=len(items), items=items)

    except Exception as e:
        logger.error(f"ค้นหารายการหุ้นไม่สำเร็จ: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"ค้นหารายการหุ้นไม่สำเร็จ: {str(e)}",
            },
        )


@router.get(
    "/{record_id}",
    response_model=AnalysisReport,
    responses={
        200: {"description": "รายละเอียดรายงาน"},
        404: {"description": "ไม่พบรายงาน", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงรายละเอียดรายงานย้อนหลัง",
    description="ดึงรายงานการวิเคราะห์ย้อนหลังฉบับเต็มตาม ID หรือ query_id"
)
def get_history_detail(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> AnalysisReport:
    """
    ดึงรายละเอียดรายงานย้อนหลัง
    
    根据分析历史记录主键 ID 或 query_id 获取完整的历史分析报告。
    优先尝试按主键 ID（整数）查询，若参数不是合法整数则按 query_id 查询。
    
    Args:
        record_id: 分析历史记录主键 ID（整数）或 query_id（字符串）
        db_manager: 数据库管理器依赖
        
    Returns:
        AnalysisReport: 完整分析报告
        
    Raises:
        HTTPException: 404 - ไม่พบรายงาน
    """
    try:
        service = HistoryService(db_manager)
        
        # Try integer ID first, fall back to query_id string lookup
        result = service.resolve_and_get_detail(record_id)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"ไม่พบบันทึกการวิเคราะห์ที่มี id/query_id={record_id}"
                }
            )
        
        # 从 context_snapshot 中提取价格信息
        # 注意：使用 `is None` 而非 `or`，避免把 0.0（平盘）误判为缺失值；
        # 同时不混用 `change_60d`（60 日累计涨跌幅）作为日内 change_pct 的兜底。
        context_snapshot = result.get("context_snapshot")
        analysis_context_pack_overview = extract_analysis_context_pack_overview(context_snapshot)
        market_phase_summary = result.get("market_phase_summary")
        if market_phase_summary is None:
            market_phase_summary = extract_market_phase_summary(context_snapshot)
        api_context_snapshot = sanitize_context_snapshot_for_api(context_snapshot)
        realtime_fields = extract_realtime_detail_fields(context_snapshot)
        current_price = realtime_fields.get("current_price")
        change_pct = realtime_fields.get("change_pct")
        
        raw_result = result.get("raw_result")
        if not isinstance(raw_result, dict):
            raw_result = {}
        report_language = normalize_report_language(
            result.get("report_language")
            or raw_result.get("report_language")
            or (
                context_snapshot.get("report_language")
                if isinstance(context_snapshot, dict)
                else None
            )
        )
        stock_name = get_localized_stock_name(
            result.get("stock_name"),
            result.get("stock_code", ""),
            report_language,
        )

        # 构建响应模型
        meta = ReportMeta(
            id=result.get("id"),
            query_id=result.get("query_id", ""),
            stock_code=result.get("stock_code", ""),
            stock_name=stock_name,
            report_type=result.get("report_type"),
            report_language=report_language,
            created_at=result.get("created_at"),
            current_price=current_price,
            change_pct=change_pct,
            model_used=normalize_model_used(result.get("model_used")),
            market_phase_summary=market_phase_summary,
            asset_type=asset_type_from_canonical_code(
                result.get("storage_stock_code") or result.get("stock_code")
            ),
        )
        
        summary = ReportSummary(
            analysis_summary=result.get("analysis_summary"),
            operation_advice=localize_operation_advice(
                result.get("operation_advice"),
                report_language,
            ),
            action=result.get("action"),
            action_label=result.get("action_label"),
            trend_prediction=localize_trend_prediction(
                result.get("trend_prediction"),
                report_language,
            ),
            sentiment_score=result.get("sentiment_score"),
            sentiment_label=(
                get_sentiment_label(result.get("sentiment_score"), report_language)
                if result.get("sentiment_score") is not None
                else result.get("sentiment_label")
            )
        )
        
        strategy = ReportStrategy(
            ideal_buy=result.get("ideal_buy"),
            secondary_buy=result.get("secondary_buy"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit")
        )
        
        fallback_fundamental = db_manager.get_latest_fundamental_snapshot(
            query_id=result.get("query_id", ""),
            code=result.get("storage_stock_code") or result.get("stock_code", ""),
        )
        extracted_fundamental = extract_fundamental_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )
        extracted_boards = extract_board_detail_fields(
            context_snapshot=result.get("context_snapshot"),
            fallback_fundamental_payload=fallback_fundamental,
        )
        market_structure = extract_market_structure_detail_field(
            result.get("context_snapshot"),
            result.get("raw_result"),
        )

        details = ReportDetails(
            news_content=result.get("news_content"),
            empty_news_disclosure=result.get("empty_news_disclosure"),
            raw_result=result.get("raw_result"),
            context_snapshot=api_context_snapshot,
            analysis_context_pack_overview=analysis_context_pack_overview,
            financial_report=extracted_fundamental.get("financial_report"),
            dividend_metrics=extracted_fundamental.get("dividend_metrics"),
            belong_boards=extracted_boards.get("belong_boards"),
            sector_rankings=extracted_boards.get("sector_rankings"),
            concept_rankings=extracted_boards.get("concept_rankings"),
            market_structure=market_structure,
        )
        
        return AnalysisReport(
            meta=meta,
            summary=summary,
            strategy=strategy,
            details=details
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ค้นหารายละเอียดย้อนหลังไม่สำเร็จ: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"ค้นหารายละเอียดย้อนหลังไม่สำเร็จ: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/diagnostics",
    response_model=RunDiagnosticSummaryResponse,
    responses={
        200: {"description": "สรุปการวินิจฉัยการรัน"},
        404: {"description": "ไม่พบรายงาน", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงสรุปการวินิจฉัยการรันของรายงานย้อนหลัง",
    description="ดึงสรุปการวินิจฉัยที่ผู้ใช้อ่านได้และข้อความสำเนาแบบปิดข้อมูลอ่อนไหว ตาม ID หรือ query_id",
)
def get_history_diagnostics(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunDiagnosticSummaryResponse:
    """
    ดึงสรุปการวินิจฉัยการรันของรายงานย้อนหลัง。
    """
    try:
        service = HistoryService(db_manager)
        summary = service.resolve_and_get_diagnostics(record_id)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"ไม่พบบันทึกการวิเคราะห์ที่มี id/query_id={record_id}",
                },
            )
        return RunDiagnosticSummaryResponse.model_validate(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ค้นหาสรุปการวินิจฉัยไม่สำเร็จ: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Querying runtime diagnostic summary failed: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/flow",
    response_model=RunFlowSnapshot,
    responses={
        200: {"description": "Runtime flow snapshot"},
        404: {"description": "ไม่พบรายงาน", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="Retrieve historical report runtime flow",
    description="Retrieve data/information flow snapshot based on analysis history record ID or query_id.",
)
def get_history_run_flow(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> RunFlowSnapshot:
    """
    获取历史报告运行流。
    """
    try:
        service = HistoryService(db_manager)
        snapshot = service.resolve_and_get_run_flow(record_id)
        if snapshot is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"ไม่พบบันทึกการวิเคราะห์ที่มี id/query_id={record_id}",
                },
            )
        return snapshot
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query runtime flow snapshot: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Failed to query runtime flow snapshot: {str(e)}",
            },
        )


@router.get(
    "/{record_id}/news",
    response_model=NewsIntelResponse,
    responses={
        200: {"description": "News intelligence list"},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="Retrieve associated news for historical report",
    description="Retrieve associated news intelligence list based on analysis history record ID (returns 200 even if empty)"
)
def get_history_news(
    record_id: str,
    limit: int = Query(20, ge=1, le=100, description="Limit on returned results"),
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> NewsIntelResponse:
    """
    获取历史报告关联新闻

    根据分析历史记录 ID 或 query_id 获取关联的新闻情报列表。
    在内部完成 record_id → query_id 的解析。

    Args:
        record_id: 分析历史记录主键 ID（整数）或 query_id（字符串）
        limit: 返回数量限制
        db_manager: 数据库管理器依赖

    Returns:
        NewsIntelResponse: 新闻情报列表
    """
    try:
        service = HistoryService(db_manager)
        items = service.resolve_and_get_news(record_id=record_id, limit=limit)

        response_items = [
            NewsIntelItem(
                title=item.get("title", ""),
                snippet=item.get("snippet"),
                url=item.get("url", "")
            )
            for item in items
        ]

        return NewsIntelResponse(
            total=len(response_items),
            items=response_items
        )

    except Exception as e:
        logger.error(f"Failed to query news intelligence: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"Failed to query news intelligence: {str(e)}"
            }
        )


@router.get(
    "/{record_id}/share-image-html",
    response_class=HTMLResponse,
    responses={
        200: {"description": "HTML for share image rendered by built-in Chromium in desktop client"},
        404: {"description": "ไม่พบรายงาน", "model": ErrorResponse},
        413: {"description": "Report content exceeds share image length limit", "model": ErrorResponse},
        500: {"description": "Report generation failed", "model": ErrorResponse},
    },
    summary="Retrieve historical report share image HTML",
    description="สร้าง HTML แบบ deterministic จากรายงานย้อนหลังและข้อมูลโครงสร้าง เพื่อใช้ถ่ายภาพหน้าจอในเครื่อง desktop เท่านั้น",
)
def get_history_share_image_html(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> HTMLResponse:
    result, markdown_content = _history_share_image_input(record_id, db_manager)
    config = get_config()
    max_chars = getattr(config, "markdown_to_image_max_chars", 15000)
    if len(markdown_content) > max_chars:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "share_image_too_large",
                "message": f"รายงานเนื้อหาเกินขีดจำกัดของรูปภาพแชร์ {max_chars} ตัวอักษร",
            },
        )

    try:
        html = build_share_image_html(
            markdown_content,
            structured_payload=_history_share_image_payload(result),
            branding=_history_share_image_branding(config),
        )
    except Exception as exc:
        logger.error("Share image HTML generation failed for %s: %s", record_id, exc)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": "การสร้างเนื้อหาภาพแชร์สำหรับโต๊ะทำงานล้มเหลว",
            },
        ) from exc

    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; img-src data:; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{record_id}/share-image",
    response_class=Response,
    responses={
        200: {"description": "รูปภาพ PNG สำหรับแชร์", "content": {"image/png": {}}},
        404: {"description": "ไม่พบรายงาน", "model": ErrorResponse},
        500: {"description": "Report generation failed", "model": ErrorResponse},
        503: {"description": "ไม่สามารถใช้งานเครื่องมือเรนเดอร์รูปภาพได้", "model": ErrorResponse},
    },
    summary="สร้างรูปภาพแชร์รายงานประวัติ",
    description="สร้างรูปภาพ PNG แชร์รายงานประวัติจากข้อมูล Markdown และข้อมูลโครงสร้างคงที่",
)
def get_history_share_image(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager),
) -> Response:
    result, markdown_content = _history_share_image_input(record_id, db_manager)

    config = get_config()
    image_bytes = markdown_to_image(
        markdown_content,
        max_chars=getattr(config, "markdown_to_image_max_chars", 15000),
        structured_payload=_history_share_image_payload(result),
    )
    if image_bytes is None:
        engine = getattr(config, "md2img_engine", "wkhtmltoimage")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "share_image_unavailable",
                "message": f"การสร้างรูปภาพแชร์ล้มเหลว กรุณาตรวจสอบว่าเครื่องมือแปลงรูป {engine} ได้ติดตั้งและใช้งานได้หรือไม่",
            },
        )

    filename = f"dsa-report-{result.get('id') or record_id}.png"
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{record_id}/markdown",
    response_model=MarkdownReportResponse,
    responses={
        200: {"description": "รายงานรูปแบบ Markdown"},
        404: {"description": "ไม่พบรายงาน", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงรูปแบบ Markdown ของรายงานประวัติ",
    description="ดึงรายงานวิเคราะห์ฉบับเต็มในรูปแบบ Markdown จาก ID ประวัติการวิเคราะห์"
)
def get_history_markdown(
    record_id: str,
    db_manager: DatabaseManager = Depends(get_database_manager)
) -> MarkdownReportResponse:
    """
    获取历史报告的 Markdown 格式内容

    根据分析历史记录 ID 或 query_id 生成与推送通知格式一致的 Markdown 报告。

    Args:
        record_id: 分析历史记录主键 ID（整数）或 query_id（字符串）
        db_manager: 数据库管理器依赖

    Returns:
        MarkdownReportResponse: Markdown 格式的完整报告

    Raises:
        HTTPException: 404 - ไม่พบรายงาน
        HTTPException: 500 - 报告生成失败（服务器内部错误）
    """
    service = HistoryService(db_manager)

    try:
        markdown_content = service.get_markdown_report(record_id)
    except MarkdownReportGenerationError as e:
        logger.error(f"Markdown report generation failed for {record_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": f"การสร้างรายงาน Markdown ล้มเหลว: {e.message}"
            }
        )
    except Exception as e:
        logger.error(f"การดึงรายงาน Markdown ล้มเหลว: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"การดึงรายงาน Markdown ล้มเหลว: {str(e)}"
            }
        )

    if markdown_content is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": f"ไม่พบบันทึกการวิเคราะห์ที่มี id/query_id={record_id}"
            }
        )

    return MarkdownReportResponse(content=markdown_content)
