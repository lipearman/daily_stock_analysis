# -*- coding: utf-8 -*-
"""
===================================
股票数据接口
===================================

职责：
1. POST /api/v1/stocks/extract-from-image สกัดรหัสหุ้นจากรูปภาพ
2. POST /api/v1/stocks/parse-import 解析 CSV/Excel/剪贴板
3. GET /api/v1/stocks/{code}/quote 实时行情接口
4. GET /api/v1/stocks/{code}/history 历史行情接口
"""

import logging
from typing import Optional
import re

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, Depends

from api.deps import get_system_config_service

from api.v1.schemas.stocks import (
    ExtractFromImageResponse,
    ExtractItem,
    KLineData,
    StockHistoryResponse,
    StockProfileResponse,
    StockQuote,
)
from api.v1.schemas.history import WatchlistRequest, WatchlistResponse
from api.v1.schemas.common import ErrorResponse
from src.services.image_stock_extractor import (
    ALLOWED_MIME,
    MAX_SIZE_BYTES,
    extract_stock_codes_from_image,
)
from src.services.import_parser import (
    MAX_FILE_BYTES,
    parse_import_from_bytes,
    parse_import_from_text,
)
from src.services.stock_service import StockService
from src.services.stock_profile_service import InvalidStockProfileCode, StockProfileService
from src.services.run_diagnostics import sanitize_diagnostic_text
from src.services.stock_list_parser import split_stock_list
from src.services.system_config_service import SystemConfigService
from data_provider.base import normalize_stock_code

logger = logging.getLogger(__name__)

router = APIRouter()

# 须在 /{stock_code} 路由之前定义
ALLOWED_MIME_STR = ", ".join(ALLOWED_MIME)


def _read_watchlist_codes(service: SystemConfigService) -> list:
    """Read STOCK_LIST codes as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    stock_list_str = ""
    for item in config_data.get("items", []):
        if item.get("key") == "STOCK_LIST":
            stock_list_str = str(item.get("value", ""))
            break
    return split_stock_list(stock_list_str)


def _write_watchlist_codes(service: SystemConfigService, codes: list) -> None:
    """Persist stock codes to STOCK_LIST as-is (no normalization)."""
    config_data = service.get_config(include_schema=False)
    config_version = config_data.get("config_version", "")
    service.update(
        config_version=config_version,
        items=[{"key": "STOCK_LIST", "value": ",".join(codes)}],
        mask_token="******",
        reload_now=True,
    )


# Stock code validation patterns (aligned with frontend validateStockCode)
_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"                              # A-share 6-digit
    r"|(?:SH|SZ|BJ)\d{6}"                     # exchange-prefixed A-share
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"                # exchange-suffixed A-share
    r"|\d{1,5}\.HK"                           # HK suffix format
    r"|HK\d{1,5}"                             # HK prefix format
    r"|\d{5}"                                 # bare 5-digit HK code
    r"|\d{4,5}\.T"                            # Japan Yahoo suffix format
    r"|\d{6}\.(?:KS|KQ)"                     # Korea Yahoo suffix format
    r"|\d{4,6}\.(?:TW|TWO)"                  # Taiwan Yahoo suffix format
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"         # US ticker
    r")$",
    re.IGNORECASE,
)


def _validate_and_normalize_stock_code(code: str) -> str:
    """Validate stock code format and return canonical form.

    Raises HTTPException(400) if the code does not match supported formats.
    """
    stripped = code.strip()
    if not stripped:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "Stock code cannot be empty"},
        )
    if not _STOCK_CODE_RE.match(stripped):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_stock_code",
                "message": f"'{stripped}' 不是合法的股票代码格式",
            },
        )
    return normalize_stock_code(stripped)


def _watchlist_match_key(code: str) -> str:
    """Return the equivalence key used for watchlist add/remove matching."""
    normalized = normalize_stock_code(code.strip())
    if re.fullmatch(r"\d{5}", normalized):
        return f"HK{normalized}"
    return normalized.upper()


@router.post(
    "/extract-from-image",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "รหัสหุ้นที่สกัดได้"},
        400: {"description": "รูปภาพไม่ถูกต้อง", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="สกัดรหัสหุ้นจากรูปภาพ",
    description="อัปโหลดภาพหน้าจอ/รูปภาพ เพื่อสกัดรหัสหุ้นด้วย Vision LLM รองรับ JPEG, PNG, WebP, GIF ขนาดสูงสุด 5MB",
)
def extract_from_image(
    file: Optional[UploadFile] = File(None, description="ไฟล์รูปภาพ (ฟอร์มฟิลด์ชื่อ file)"),
    include_raw: bool = Query(False, description="รวมข้อความตอบดิบของ LLM ในผลลัพธ์หรือไม่"),
) -> ExtractFromImageResponse:
    """
    从上传的图片中提取股票代码（使用 Vision LLM）。

    表单字段请使用 file 上传图片。优先级：Gemini / Anthropic / OpenAI（首个可用）。
    """
    if not file or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_request", "message": "ยังไม่ได้แนบไฟล์ โปรดอัปโหลดรูปผ่านฟอร์มฟิลด์ file"},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_type",
                "message": f"ประเภทที่ไม่รองรับ: {content_type} ที่อนุญาต: {ALLOWED_MIME_STR}",
            },
        )

    try:
        # 先读取限定大小，再检查是否还有剩余（语义清晰：超出则拒绝）
        data = file.file.read(MAX_SIZE_BYTES)
        if file.file.read(1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"รูปภาพเกินขีดจำกัด {MAX_SIZE_BYTES // (1024 * 1024)}MB",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"ไม่สามารถอ่านไฟล์ที่อัปโหลดได้: {e}")
        raise HTTPException(
            status_code=400,
            detail={"error": "read_failed", "message": "ไม่สามารถอ่านไฟล์ที่อัปโหลดได้"},
        )

    try:
        items, raw_text = extract_stock_codes_from_image(data, content_type)
        extract_items = [
            ExtractItem(code=code, name=name, confidence=conf) for code, name, conf in items
        ]
        codes = [i.code for i in extract_items]
        return ExtractFromImageResponse(
            codes=codes,
            items=extract_items,
            raw_text=raw_text if include_raw else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "extract_failed", "message": str(e)})
    except Exception as e:
        logger.error(f"การดึงข้อมูลจากภาพล้มเหลว: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "การดึงข้อมูลจากภาพล้มเหลว"},
        )


@router.post(
    "/parse-import",
    response_model=ExtractFromImageResponse,
    responses={
        200: {"description": "ผลลัพธ์การวิเคราะห์"},
        400: {"description": "ไม่ได้รับข้อมูลหรือการวิเคราะห์ล้มเหลว", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="การวิเคราะห์ CSV/Excel/คลิปบัดกรี",
    description="Upload CSV/Excel files or paste text, automatically parse stock codes. Maximum file size 2MB, text size limit 100KB.",
)
async def parse_import(request: Request) -> ExtractFromImageResponse:
    """
    解析 CSV/Excel 文件或剪贴板文本。

    - multipart/form-data + file: 上传文件
    - application/json + {"text": "..."}: 粘贴文本
    - 优先使用 file，若同时提供则忽略 text
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("[parse_import] JSON parse failed: %s", e)
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_json", "message": f"การวิเคราะห์ JSON ล้มเหลว: {e}"},
            )
        text = body.get("text") if isinstance(body, dict) else None
        if not text or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "ไม่ได้ระบุ text กรุณาใช้ {\\\"text\\\": \\\"...\\\"}"},
            )
        try:
            items = parse_import_from_text(text)
        except ValueError as e:
            text_bytes = len(text.encode("utf-8"))
            logger.warning(
                "[parse_import] parse_import_from_text failed: text_bytes=%d, error=%s",
                text_bytes,
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    elif "multipart" in content_type:
        form = await request.form()
        file = form.get("file")
        if not file or not hasattr(file, "read"):
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_request", "message": "ไม่ได้ระบุไฟล์ กรุณาใช้ฟิลด์แบบฟอร์ม file"},
            )
        file_size = getattr(file, "size", None)
        if isinstance(file_size, int) and file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "file_too_large",
                    "message": f"ไฟล์เกินขนาด {MAX_FILE_BYTES // (1024 * 1024)}MB",
                },
            )
        try:
            data = file.file.read(MAX_FILE_BYTES)
            if file.file.read(1):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "file_too_large",
                        "message": f"ไฟล์เกินขนาด {MAX_FILE_BYTES // (1024 * 1024)}MB",
                    },
                )
        except HTTPException:
            raise
        except Exception as e:
            filename = getattr(file, "filename", None) or ""
            size = getattr(file, "size", None)
            logger.warning(
                "[parse_import] file read failed: filename=%r, size=%s, error=%s",
                filename,
                size,
                e,
            )
            raise HTTPException(
                status_code=400,
                detail={"error": "read_failed", "message": "ไม่สามารถอ่านไฟล์ได้"},
            )
        filename = getattr(file, "filename", None) or ""
        try:
            items = parse_import_from_bytes(data, filename=filename)
        except ValueError as e:
            ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            logger.warning(
                "[parse_import] parse_import_from_bytes failed: filename=%r, ext=%r, bytes=%d, error=%s",
                filename,
                ext,
                len(data),
                e,
            )
            raise HTTPException(status_code=400, detail={"error": "parse_failed", "message": str(e)})
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_request",
                "message": "กรุณาใช้ multipart/form-data เพื่ออัปโหลดไฟล์ หรือ application/json เพื่อส่ง {\\\"text\\\": \\\"...\\\"}",
            },
        )

    extract_items = [
        ExtractItem(code=code, name=name, confidence=conf)
        for code, name, conf in items
    ]
    codes = list(dict.fromkeys(i.code for i in extract_items if i.code))
    return ExtractFromImageResponse(codes=codes, items=extract_items, raw_text=None)


@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "รายการหุ้นที่เลือกไว้ปัจจุบัน"},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงรายการหุ้นที่เลือกไว้",
    description="คืนค่ารหัสหุ้นทั้งหมดจากตั้งค่า STOCK_LIST ปัจจุบัน",
)
def get_watchlist(
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        codes = _read_watchlist_codes(service)
        return WatchlistResponse(stock_codes=codes, message=f"หุ้นที่เลือกไว้ปัจจุบันมีทั้งหมด {len(codes)} ตัว")
    except Exception as e:
        logger.error(f"ล้มเหลวในการดึงรายการหุ้นที่เลือกไว้: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"ล้มเหลวในการดึงรายการหุ้นที่เลือกไว้: {str(e)}"},
        )


@router.post(
    "/watchlist/add",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "ได้เพิ่มเข้าไปในรายการหุ้นที่เลือกไว้แล้ว"},
        400: {"description": "ข้อมูลพารามิเตอร์ผิดพลาด", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="เพิ่มเข้าไปในรายการหุ้นที่เลือกไว้",
    description="เพิ่มรหัสหุ้นที่ระบุไว้ลงใน STOCK_LIST",
)
def add_to_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        if _watchlist_match_key(validated) not in existing_keys:
            codes.append(request.stock_code.strip())
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"ได้เพิ่มเข้าไปแล้วใน {request.stock_code.strip()}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ล้มเหลวในการเพิ่มเข้าไปในรายการหุ้นที่เลือกไว้: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"ล้มเหลวในการเพิ่มเข้าไปในรายการหุ้นที่เลือกไว้: {str(e)}"},
        )


@router.post(
    "/watchlist/remove",
    response_model=WatchlistResponse,
    responses={
        200: {"description": "ได้ลบออกจากรายการหุ้นที่เลือกไว้แล้ว"},
        400: {"description": "ข้อมูลพารามิเตอร์ผิดพลาด", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ลบออกจากรายการหุ้นที่เลือกไว้",
    description="ลบรหัสหุ้นที่ระบุไว้ออกจาก STOCK_LIST",
)
def remove_from_watchlist(
    request: WatchlistRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> WatchlistResponse:
    try:
        validated = _validate_and_normalize_stock_code(request.stock_code)
        codes = _read_watchlist_codes(service)
        existing_keys = [_watchlist_match_key(c) for c in codes]
        requested_key = _watchlist_match_key(validated)
        if requested_key in existing_keys:
            idx = existing_keys.index(requested_key)
            codes.pop(idx)
            _write_watchlist_codes(service, codes)
        return WatchlistResponse(stock_codes=codes, message=f"ได้ลบ {request.stock_code.strip()} ออกแล้ว")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ล้มเหลวในการลบออกจากรายการหุ้นที่เลือกไว้: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": f"ล้มเหลวในการลบออกจากรายการหุ้นที่เลือกไว้: {str(e)}"},
        )


@router.get(
    "/{stock_code}/profile",
    response_model=StockProfileResponse,
    responses={
        400: {"description": "รหัสหุ้นไม่ถูกต้อง", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงข้อมูลรวมการวิจัยหุ้นรายตัว",
    description="รวมข้อมูลตลาด ประวัติการเคลื่อนไหว การวิจัยผลิตภัณฑ์ ข่าวสาร ความสัมพันธ์การถือหุ้น และกฎควบคุมตามสถานะคุณภาพอิสระ",
)
def get_stock_profile(
    stock_code: str,
    history_days: int = Query(60, ge=1, le=365, description="จำนวนวันประวัติการเคลื่อนไหวรายวัน"),
) -> StockProfileResponse:
    """Return partial profile data without failing on one optional block."""
    _validate_and_normalize_stock_code(stock_code)
    try:
        return StockProfileResponse(
            **StockProfileService().get_profile(stock_code, history_days=history_days)
        )
    except InvalidStockProfileCode:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_stock_code", "message": "รหัสหุ้นไม่ตรงกับตลาดหลักทรัพย์"},
        )
    except Exception as exc:
        sanitized = sanitize_diagnostic_text(str(exc), max_length=300) or "internal profile error"
        logger.error("ล้มเหลวในการดึงข้อมูลรวมการวิจัยหุ้นรายตัว: %s", sanitized)
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": "ล้มเหลวในการดึงข้อมูลรวมการวิจัยหุ้นรายตัว"},
        )


@router.get(
    "/{stock_code}/quote",
    response_model=StockQuote,
    responses={
        200: {"description": "ข้อมูลราคาตลาด"},
        404: {"description": "ไม่พบหุ้นนี้", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงราคาเรียลไทม์ของหุ้น",
    description="ดึงข้อมูลราคาล่าสุดของหุ้นที่ระบุ"
)
def get_stock_quote(stock_code: str) -> StockQuote:
    """
    ดึงราคาเรียลไทม์ของหุ้น
    
    ดึงข้อมูลราคาล่าสุดของหุ้นที่ระบุ
    
    Args:
        stock_code: 股票代码（如 600519、00700、AAPL）
        
    Returns:
        StockQuote: 实时ข้อมูลราคาตลาด
        
    Raises:
        HTTPException: 404 - ไม่พบหุ้นนี้
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_realtime_quote(stock_code)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "not_found",
                    "message": f"ไม่พบข้อมูลราคาหุ้น {stock_code}"
                }
            )
        
        return StockQuote(
            stock_code=result.get("stock_code", stock_code),
            stock_name=result.get("stock_name"),
            current_price=result.get("current_price", 0.0),
            change=result.get("change"),
            change_percent=result.get("change_percent"),
            open=result.get("open"),
            high=result.get("high"),
            low=result.get("low"),
            prev_close=result.get("prev_close"),
            volume=result.get("volume"),
            amount=result.get("amount"),
            update_time=result.get("update_time")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"การดึงข้อมูลราคาจริงล้มเหลว: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"การดึงข้อมูลราคาจริงล้มเหลว: {str(e)}"
            }
        )


@router.get(
    "/{stock_code}/history",
    response_model=StockHistoryResponse,
    responses={
        200: {"description": "ข้อมูลราคาหุ้นตามเวลาอดีต"},
        422: {"description": "พารามิเตอร์รอบเวลาที่ไม่รองรับ", "model": ErrorResponse},
        500: {"description": "ข้อผิดพลาดของเซิร์ฟเวอร์", "model": ErrorResponse},
    },
    summary="ดึงข้อมูลราคาหุ้นตามเวลาอดีต",
    description="ดึงข้อมูลกราฟ K ตามหุ้นที่ระบุไว้"
)
def get_stock_history(
    stock_code: str,
    period: str = Query("daily", description="รอบเวลากราฟ K", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365, description="จำนวนวันที่ต้องการดึง")
) -> StockHistoryResponse:
    """
    获取股票历史行情
    
    获取指定股票的历史 K 线数据
    
    Args:
        stock_code: 股票代码
        period: K 线周期 (daily/weekly/monthly)
        days: 获取天数
        
    Returns:
        StockHistoryResponse: 历史ข้อมูลราคาตลาด
    """
    try:
        service = StockService()
        
        # 使用 def 而非 async def，FastAPI 自动在线程池中执行
        result = service.get_history_data(
            stock_code=stock_code,
            period=period,
            days=days
        )
        
        # 转换为响应模型
        data = [
            KLineData(
                date=item.get("date"),
                open=item.get("open"),
                high=item.get("high"),
                low=item.get("low"),
                close=item.get("close"),
                volume=item.get("volume"),
                amount=item.get("amount"),
                change_percent=item.get("change_percent")
            )
            for item in result.get("data", [])
        ]
        
        return StockHistoryResponse(
            stock_code=stock_code,
            stock_name=result.get("stock_name"),
            period=period,
            data=data
        )
    
    except ValueError as e:
        # period 参数不支持的错误（如 weekly/monthly）
        raise HTTPException(
            status_code=422,
            detail={
                "error": "unsupported_period",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"การดึงข้อมูลราคาหุ้นตามเวลาอดีตล้มเหลว: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": f"การดึงข้อมิูลราคาหุ้นตามเวลาอดีตล้มเหลว: {str(e)}"
            }
        )
