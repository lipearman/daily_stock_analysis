# -*- coding: utf-8 -*-
"""DecisionSignal API endpoints."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyCookie

from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.decision_signals import (
    DecisionSignalCreateRequest,
    DecisionSignalFeedbackItem,
    DecisionSignalFeedbackRequest,
    DecisionSignalItem,
    DecisionSignalListResponse,
    DecisionSignalMutationResponse,
    DecisionSignalOutcomeListResponse,
    DecisionSignalOutcomeRunRequest,
    DecisionSignalOutcomeRunResponse,
    DecisionSignalOutcomeStatsResponse,
    DecisionSignalReassessRequest,
    DecisionSignalReassessErrorResponse,
    DecisionSignalReassessResponse,
    DecisionSignalReviewMemory,
    DecisionSignalStatusUpdateRequest,
)
from src.auth import COOKIE_NAME
from src.services.decision_signal_service import (
    DecisionSignalNotFoundError,
    DecisionSignalService,
    DecisionSignalStorageError,
)
from src.services.decision_signal_outcome_service import DecisionSignalOutcomeService
from src.services.decision_signal_reassess_service import (
    DecisionSignalReassessGuardrailBlockedError,
    DecisionSignalReassessService,
    DecisionSignalSourceReportNotFoundError,
    DecisionSignalUnsupportedReportSnapshotError,
    DecisionSignalUnsupportedReportTypeError,
)


logger = logging.getLogger(__name__)

admin_session_cookie = APIKeyCookie(
    name=COOKIE_NAME,
    scheme_name="AdminSessionCookie",
    auto_error=False,
)
router = APIRouter(dependencies=[Security(admin_session_cookie)])

AUTH_RESPONSE = {
    401: {
        "model": ErrorResponse,
        "description": "ยังไม่ได้เข้าสู่ระบบ หรือเซสชันผู้ดูแลหมดอายุ (เมื่อ ADMIN_AUTH_ENABLED=true)",
    },
}


def _bad_request(exc: Exception, *, error: str = "validation_error") -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"error": error, "message": str(exc)},
    )


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "not_found", "message": str(exc)},
    )


def _error(status_code: int, exc: Exception, *, error: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": error, "message": str(exc)},
    )


def _internal_error(message: str, exc: Exception) -> HTTPException:
    logger.error("%s: %s", message, exc, exc_info=True)
    return HTTPException(
        status_code=500,
        detail={"error": "internal_error", "message": message},
    )


def _guardrail_blocked(exc: DecisionSignalReassessGuardrailBlockedError) -> HTTPException:
    response = DecisionSignalReassessErrorResponse(
        error="guardrail_blocked",
        message="Reassessed decision signal was blocked by guardrail.",
        blocked_reason=exc.blocked_reason,
        warnings=exc.warnings,
    )
    return HTTPException(status_code=400, detail=response.model_dump())


@router.post(
    "",
    response_model=DecisionSignalMutationResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "ฟิลด์ที่ส่งมาไม่ถูกต้อง"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบรูปแบบข้อมูลร้องขอหรือพารามิเตอร์เส้นทางล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การสร้างล้มเหลว"},
    },
    summary="สร้างหรือลบซ้ำสัญญาณตัดสินใจ",
    description=(
        "เขียนสัญญาณตัดสินใจอย่างชัดเจน โดยหากไม่ได้ส่ง horizon/expires_at จะให้บริการเติมเต็มช่วงเวลาค่าเริ่มต้นโดยอัตโนมัติ;"
        "เมื่อพบกับกุญแจซ้ำหรือการลบซ้ำแบบผ่อนปรนจะคืนข้อมูลเดิมพร้อม created=false;"
        "เมื่อสร้างสัญญาณใหม่หรือยืดอายุสัญญาณที่หมดอายุแล้วจะทำให้สัญญาณ active เดิมหายไป;"
        "การพยายามซ้ำสัญญาณ active duplicate จะทำซ้ำการแก้ไขครั้งเดิม ส่วนการซ้ำแบบปกติจะไม่ถือเป็นเหตุการณ์การเปิดใช้งานใหม่;"
        "ไม่รับประกันความเท่าเทียมแบบสมบูรณ์ภายใต้การประมวลผลพร้อมกัน"
    ),
    operation_id="createDecisionSignal",
)
def create_signal(request: DecisionSignalCreateRequest) -> DecisionSignalMutationResponse:
    service = DecisionSignalService()
    try:
        payload = request.model_dump(exclude_unset=True)
        return DecisionSignalMutationResponse(**service.create_signal(payload))
    except DecisionSignalStorageError as exc:
        raise _internal_error("Create decision signal failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Create decision signal failed", exc)


@router.get(
    "",
    response_model=DecisionSignalListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "พารามิเตอร์การค้นหาไม่ถูกต้อง"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบพารามิเตอร์การค้นหาล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ดึงรายการสัญญาณตัดสินใจ",
    description=(
        "ดึงรายการ DecisionSignal แบบแบ่งหน้า โดยก่อนอ่านจะตรวจสอบและล่าช้าการหมดอายุของสัญญาณ active ที่ถึง expires_at"
        "เมื่อ source_type=analysis และส่งเฉพาะ source_report_id มาในการค้นหา หากไม่พบสัญญาณจะพยายามเติมกลับแบบล่าช้าจากรายงานประวัตินี้"
        "(เฉพาะในสถานการณ์ครั้งแรกที่พบรายการ และการค้นหาแบบแม่นยำนี้จะกระตุ้นให้เติมกลับสัญญาณตัดสินใจจากอดีต ซึ่งเป็นพฤติกรรมแบบ read-with-write;"
        "ไม่กระทบต่อพารามิเตอร์กรองรายการอื่นๆ ในสถานการณ์แบ่งหน้า)"
        "holding_only=true only reads cached portfolio_positions for active accounts, does not trigger portfolio snapshot replay."
    ),
    operation_id="listDecisionSignals",
)
def list_signals(
    market: Optional[str] = Query(None, description="Optional market filter: cn/hk/us/jp/kr/tw"),
    stock_code: Optional[str] = Query(None, description="Optional stock code filter"),
    action: Optional[str] = Query(None, description="Optional decision action filter"),
    market_phase: Optional[str] = Query(None, description="Optional market phase filter"),
    decision_profile: Optional[str] = Query(
        None,
        description="Optional decision profile filter: conservative/balanced/aggressive/unknown",
    ),
    source_type: Optional[str] = Query(None, description="Optional source type filter"),
    source_report_id: Optional[int] = Query(None, description="Optional source report id filter"),
    trace_id: Optional[str] = Query(None, description="Optional trace id filter"),
    trigger_source: Optional[str] = Query(None, description="Optional trigger source filter"),
    status: Optional[str] = Query(None, description="Optional status filter"),
    created_from: Optional[str] = Query(None, description="Inclusive created_at lower bound"),
    created_to: Optional[str] = Query(None, description="Inclusive created_at upper bound"),
    expires_from: Optional[str] = Query(None, description="Inclusive expires_at lower bound"),
    expires_to: Optional[str] = Query(None, description="Inclusive expires_at upper bound"),
    holding_only: bool = Query(False, description="Filter to active cached portfolio holdings only"),
    account_id: Optional[int] = Query(
        None,
        description="Optional active portfolio account id for holding_only",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DecisionSignalListResponse:
    service = DecisionSignalService()
    try:
        return DecisionSignalListResponse(
            **service.list_signals(
                market=market,
                stock_code=stock_code,
                action=action,
                market_phase=market_phase,
                decision_profile=decision_profile,
                source_type=source_type,
                source_report_id=source_report_id,
                trace_id=trace_id,
                trigger_source=trigger_source,
                status=status,
                created_from=created_from,
                created_to=created_to,
                expires_from=expires_from,
                expires_to=expires_to,
                holding_only=holding_only,
                account_id=account_id,
                page=page,
                page_size=page_size,
            )
        )
    except DecisionSignalStorageError as exc:
        raise _internal_error("List decision signals failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List decision signals failed", exc)


@router.post(
    "/outcomes/run",
    response_model=DecisionSignalOutcomeRunResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "ฟิลด์ที่ส่งมาไม่ถูกต้อง"},
        404: {"model": ErrorResponse, "description": "ไม่มีสัญญาณ"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบรูปแบบร่างข้อมูลล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การคำนวณหลังเหตุการณ์ล้มเหลว"},
    },
    summary="ประเมินผลหลังเหตุการณ์สัญญาณตัดสินใจ",
    description=(
        "กระตุ้นการคำนวณผลลัพธ์ระดับสัญญาณอย่างชัดเจน โดยค่า default จะข้าม completed และสถานะสุดท้าย unable"
        "แต่จะคำนวณใหม่หากขาดข้อมูลราคาหรืออื่นๆ ที่สามารถฟื้นคืนได้ โดยที่ force=true จะคำนวณใหม่และทับซ้อนข้อมูลเดิม"
        "signal_id+horizon+engine_version。"
    ),
    operation_id="runDecisionSignalOutcomes",
)
def run_outcomes(request: DecisionSignalOutcomeRunRequest) -> DecisionSignalOutcomeRunResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeRunResponse(
            **service.run_outcomes(
                signal_id=request.signal_id,
                horizons=request.horizons,
                force=request.force,
                market=request.market,
                stock_code=request.stock_code,
                action=request.action,
                source_type=request.source_type,
                status=request.status,
                limit=request.limit,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Run decision signal outcomes failed", exc)


@router.get(
    "/outcomes",
    response_model=DecisionSignalOutcomeListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "พารามิเตอร์การค้นหาไม่ถูกต้อง"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบพารามิเตอร์การค้นหาล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ตรวจสอบผลลัพธ์หลังการตัดสินใจของสัญญาณ",
    description="ดึงข้อมูลผลลัพธ์ระดับสัญญาณ (signal-level outcome) แบบแบ่งหน้า โดยค่าเริ่มต้นจะดึงเฉพาะผลลัพธ์หลังการตัดสินใจของสัญญาณปัจจุบันใน engine_version",
    operation_id="listDecisionSignalOutcomes",
)
def list_outcomes(
    signal_id: Optional[int] = Query(None, gt=0),
    horizon: Optional[str] = Query(None),
    engine_version: Optional[str] = Query(None),
    eval_status: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DecisionSignalOutcomeListResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeListResponse(
            **service.list_outcomes(
                signal_id=signal_id,
                horizon=horizon,
                engine_version=engine_version,
                eval_status=eval_status,
                outcome=outcome,
                page=page,
                page_size=page_size,
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("List decision signal outcomes failed", exc)


@router.get(
    "/outcomes/stats",
    response_model=DecisionSignalOutcomeStatsResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "พารามิเตอร์การค้นหาไม่ถูกต้อง"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบพารามิเตอร์การค้นหาล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การนับรวมล้มเหลว"},
    },
    summary="ตรวจสอบสถิติผลลัพธ์หลังการตัดสินใจของสัญญาณ",
    description="ค่าเริ่มต้นจะนับรวมข้อมูลจาก engine_version ปัจจุบัน และจะตัดสัญญาณที่ถูกลบออกไป",
    operation_id="getDecisionSignalOutcomeStats",
)
def get_outcome_stats(
    horizons: Optional[List[str]] = Query(None),
    engine_version: Optional[str] = Query(None),
    statuses: Optional[List[str]] = Query(None),
) -> DecisionSignalOutcomeStatsResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeStatsResponse(
            **service.get_stats(
                horizons=horizons,
                engine_version=engine_version,
                statuses=statuses,
            )
        )
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal outcome stats failed", exc)


@router.get(
    "/stocks/{stock_code}/review",
    response_model=DecisionSignalReviewMemory,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "พารามิเตอร์การค้นหาไม่ถูกต้อง"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบเส้นทางหรือพารามิเตอร์การค้นหาล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ดูสรุปผลการวิเคราะห์การตัดสินใจของสัญญาณรายหุ้น",
    description=(
        "รวมข้อมูลผลลัพธ์ระดับสัญญาณ (signal-level outcome/feedback) จากหุ้นที่ระบุไว้ใน engine_version ปัจจุบัน"
        "คืนสรุปเฉพาะการอ่านข้อมูลที่ปลอดภัยต่ำ (low-sensitivity ReviewMemory) โดยหากตัวอย่างไม่เพียงพอ อัตรา unable สูง หรือคุณภาพข้อมูลแย่"
        "ค่า confidence_adjustment จะถูกตั้งค่าคงที่เป็น observe เพื่อใช้สำหรับการสังเกตเท่านั้น และไม่ใช่สัญญาณการซื้อขาย"
    ),
    operation_id="getDecisionSignalStockReview",
)
def get_stock_review(
    stock_code: str,
    horizon: Optional[str] = Query(None, description="Optional outcome horizon filter: 1d/3d/5d/10d"),
) -> DecisionSignalReviewMemory:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalReviewMemory(**service.get_stock_review(stock_code, horizon=horizon))
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal stock review failed", exc)


@router.post(
    "/reassess",
    response_model=DecisionSignalReassessResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": DecisionSignalReassessErrorResponse, "description": "รายงานประวัติไม่สามารถใช้งานได้หรือถูกปิดกั้นโดยระบบควบคุมความเสี่ยง"},
        404: {"model": ErrorResponse, "description": "รายงานประวัติแหล่งที่มาไม่มีอยู่"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบรูปแบบร่างข้อมูลล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การประเมินใหม่ล้มเหลว"},
    },
    summary="ประเมินรูปแบบการตัดสินใจใหม่ และเลือกเก็บรักษาไว้",
    description=(
        "คำนวณสัญญาณ decision_profile อีกครั้งจากภาพสำเนาประวัติรายงานที่เก็บไว้ตาม source_report_id"
        "หาก persist=false จะคืนภาพรวมอ่านได้เพียงเท่านั้น ส่วน persist=true จะบันทึกผลลัพธ์จากเซิร์ฟเวอร์ guardrail เข้าไปใน DecisionSignal"
    ),
    operation_id="reassessDecisionSignalPreview",
)
def reassess_signal(request: DecisionSignalReassessRequest) -> DecisionSignalReassessResponse:
    service = DecisionSignalReassessService()
    try:
        return DecisionSignalReassessResponse(
            **service.reassess(
                source_report_id=request.source_report_id,
                decision_profile=request.decision_profile,
                persist=request.persist,
            )
        )
    except DecisionSignalSourceReportNotFoundError as exc:
        raise _error(404, exc, error="source_report_not_found")
    except DecisionSignalUnsupportedReportTypeError as exc:
        raise _error(400, exc, error="unsupported_report_type")
    except DecisionSignalUnsupportedReportSnapshotError as exc:
        raise _error(400, exc, error="unsupported_report_snapshot")
    except DecisionSignalReassessGuardrailBlockedError as exc:
        raise _guardrail_blocked(exc)
    except Exception as exc:
        raise _internal_error("Reassess decision signal failed", exc)


@router.get(
    "/latest/{stock_code}",
    response_model=DecisionSignalListResponse,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "พารามิเตอร์คำขอไม่ถูกต้อง"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบเส้นทางหรือพารามิเตอร์การค้นหาล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ดูสัญญาณการตัดสินใจที่เป็นไปอยู่ (active) ล่าสุดของหุ้น",
    description="คืนรายการสัญญาณการตัดสินใจที่เป็นไปอยู่ (active) ล่าสุดของหุ้นที่ระบุไว้ โดยก่อนอ่านจะดำเนินการตรวจสอบการหมดอายุแบบล่าช้า",
    operation_id="getLatestDecisionSignals",
)
def get_latest_active(
    stock_code: str,
    market: Optional[str] = Query(None, description="Optional market filter: cn/hk/us/jp/kr/tw"),
    limit: int = Query(1, ge=1, le=100),
) -> DecisionSignalListResponse:
    service = DecisionSignalService()
    try:
        return DecisionSignalListResponse(
            **service.get_latest_active(
                stock_code=stock_code,
                market=market,
                limit=limit,
            )
        )
    except DecisionSignalStorageError as exc:
        raise _internal_error("Get latest decision signals failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Get latest decision signals failed", exc)


@router.get(
    "/{signal_id}",
    response_model=DecisionSignalItem,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "ไม่มีสัญญาณ"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบพารามิเตอร์เส้นทางล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ดูสัญญาณการตัดสินใจรายรายการ",
    description="ดู DecisionSignal รายการเดียวตาม ID โดยก่อนอ่านจะดำเนินการตรวจสอบการหมดอายุแบบล่าช้า",
    operation_id="getDecisionSignal",
)
def get_signal(signal_id: int) -> DecisionSignalItem:
    service = DecisionSignalService()
    try:
        return DecisionSignalItem(**service.get_signal(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except DecisionSignalStorageError as exc:
        raise _internal_error("Get decision signal failed", exc)
    except Exception as exc:
        raise _internal_error("Get decision signal failed", exc)


@router.get(
    "/{signal_id}/outcomes",
    response_model=DecisionSignalOutcomeListResponse,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "ไม่มีสัญญาณ"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบพารามิเตอร์เส้นทางล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ดูผลลัพธ์หลังการตัดสินใจของสัญญาณการตัดสินใจรายรายการ",
    description="คืนผลลัพธ์หลังการตัดสินใจของสัญญาณตาม signal_id ใน engine_version ปัจจุบัน",
    operation_id="listDecisionSignalOutcomesBySignal",
)
def list_signal_outcomes(signal_id: int) -> DecisionSignalOutcomeListResponse:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalOutcomeListResponse(**service.list_signal_outcomes(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except Exception as exc:
        raise _internal_error("List decision signal outcomes failed", exc)


@router.get(
    "/{signal_id}/feedback",
    response_model=DecisionSignalFeedbackItem,
    responses={
        **AUTH_RESPONSE,
        404: {"model": ErrorResponse, "description": "ไม่มีสัญญาณ"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบพารามิเตอร์เส้นทางล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การค้นหาล้มเหลว"},
    },
    summary="ดูข้อเสนอแนะจากผู้ใช้งานเกี่ยวกับสัญญาณการตัดสินใจ",
    description="หากไม่มีข้อเสนอแนะจะคืน feedback_value=null หากสัญญาณไม่มีอยู่จะคืนค่า 404",
    operation_id="getDecisionSignalFeedback",
)
def get_feedback(signal_id: int) -> DecisionSignalFeedbackItem:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalFeedbackItem(**service.get_feedback(signal_id))
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except Exception as exc:
        raise _internal_error("Get decision signal feedback failed", exc)


@router.put(
    "/{signal_id}/feedback",
    response_model=DecisionSignalFeedbackItem,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "ฟิลด์ที่ส่งมาไม่ถูกต้อง"},
        404: {"model": ErrorResponse, "description": "ไม่มีสัญญาณ"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบรูปแบบข้อมูลร้องขอหรือพารามิเตอร์เส้นทางล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การอัปเดตล้มเหลว"},
    },
    summary="บันทึกข้อเสนอแนะจากผู้ใช้งานเกี่ยวกับสัญญาณการตัดสินใจ",
    description="อัปเดตข้อเสนอแนะ useful/not_useful ล่าสุดตาม signal_id",
    operation_id="putDecisionSignalFeedback",
)
def put_feedback(signal_id: int, request: DecisionSignalFeedbackRequest) -> DecisionSignalFeedbackItem:
    service = DecisionSignalOutcomeService()
    try:
        return DecisionSignalFeedbackItem(
            **service.put_feedback(
                signal_id,
                feedback_value=request.feedback_value,
                reason_code=request.reason_code,
                note=request.note,
                source=request.source,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Put decision signal feedback failed", exc)


@router.patch(
    "/{signal_id}/status",
    response_model=DecisionSignalItem,
    responses={
        **AUTH_RESPONSE,
        400: {"model": ErrorResponse, "description": "สถานะไม่ถูกต้อง"},
        404: {"model": ErrorResponse, "description": "ไม่มีสัญญาณ"},
        422: {"model": ErrorResponse, "description": "การตรวจสอบรูปแบบข้อมูลร้องขอหรือพารามิเตอร์เส้นทางล้มเหลว"},
        500: {"model": ErrorResponse, "description": "การอัปเดตล้มเหลว"},
    },
    summary="อัปเดตสถานะสัญญาณการตัดสินใจ",
    description=(
        "อัปเดตเฉพาะสถานะที่ถูกต้องและ metadata ที่เลือกใช้ได้ หากไม่ระบุ metadata จะคงค่าเดิม หากเป็น null จะล้างค่าออก"
        "เมื่อเป็น object จะแทนที่ทั้งชุดข้อมูลและรักษาตัวตนของ decision_profile อย่างเป็นทางการไว้"
        "สถานะสุดท้าย เช่น expired/invalidated/closed/archived ไม่สามารถเปลี่ยนกลับเป็น active โดยตรงได้"
    ),
    operation_id="updateDecisionSignalStatus",
)
def update_status(signal_id: int, request: DecisionSignalStatusUpdateRequest) -> DecisionSignalItem:
    service = DecisionSignalService()
    try:
        return DecisionSignalItem(
            **service.update_status(
                signal_id,
                status=request.status,
                metadata=request.metadata,
                replace_metadata="metadata" in request.model_fields_set,
            )
        )
    except DecisionSignalNotFoundError as exc:
        raise _not_found(exc)
    except DecisionSignalStorageError as exc:
        raise _internal_error("Update decision signal status failed", exc)
    except ValueError as exc:
        raise _bad_request(exc)
    except Exception as exc:
        raise _internal_error("Update decision signal status failed", exc)
