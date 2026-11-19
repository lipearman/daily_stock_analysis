# -*- coding: utf-8 -*-
"""Market phase summary schemas."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


MarketPhaseValue = Literal[
    "premarket",
    "intraday",
    "lunch_break",
    "closing_auction",
    "postmarket",
    "non_trading",
    "unknown",
]


class MarketPhaseSummary(BaseModel):
    """Low-sensitivity market phase metadata exposed on report meta."""

    market: Optional[str] = Field(None, description="market region")
    phase: MarketPhaseValue = Field(..., description="market phase")
    market_local_time: Optional[str] = Field(None, description="market local time")
    session_date: Optional[str] = Field(None, description="market local date")
    effective_daily_bar_date: Optional[str] = Field(None, description="latest reusable complete daily date")
    is_trading_day: Optional[bool] = Field(None, description="is trading day")
    is_market_open_now: Optional[bool] = Field(None, description="is market open now")
    is_partial_bar: Optional[bool] = Field(None, description="may latest daily line be incomplete")
    minutes_to_open: Optional[int] = Field(None, description="minutes until market open")
    minutes_to_close: Optional[int] = Field(None, description="minutes until market close")
    trigger_source: Optional[str] = Field(None, description="แหล่งที่มาของการกระตุ้น")
    analysis_intent: Optional[str] = Field(None, description="analysis intent")
    warnings: List[str] = Field(default_factory=list, description="phase inference downgrade alert code")
