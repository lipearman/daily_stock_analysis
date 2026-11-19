# -*- coding: utf-8 -*-
"""
===================================
股票数据相关模型
===================================

职责：
1. 定义股票实时行情模型
2. 定义历史 K 线数据模型
"""

from typing import Dict, Literal, Optional, List

from pydantic import BaseModel, ConfigDict, Field

from api.v1.schemas.history import HistoryItem
from api.v1.schemas.intelligence import IntelligenceItem
from api.v1.schemas.research_artifact import ResearchArtifact

StockProfileStatus = Literal["fresh", "partial", "unavailable"]


class StockQuote(BaseModel):
    """real-time stock market data"""
    
    stock_code: str = Field(..., description="Stock code")
    stock_name: Optional[str] = Field(None, description="Stock name")
    current_price: float = Field(..., description="current price")
    change: Optional[float] = Field(None, description="price change amount")
    change_percent: Optional[float] = Field(None, description="price change (%)")
    open: Optional[float] = Field(None, description="opening price")
    high: Optional[float] = Field(None, description="highest price")
    low: Optional[float] = Field(None, description="lowest price")
    prev_close: Optional[float] = Field(None, description="previous closing price")
    volume: Optional[float] = Field(None, description="volume (shares)")
    amount: Optional[float] = Field(None, description="turnover amount (CNY)")
    update_time: Optional[str] = Field(None, description="update time")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "Guizhou Maotai",
            "current_price": 1800.00,
            "change": 15.00,
            "change_percent": 0.84,
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "prev_close": 1785.00,
            "volume": 10000000,
            "amount": 18000000000,
            "update_time": "2024-01-01T15:00:00"
        }
    })


class KLineData(BaseModel):
    """K-line data point"""
    
    date: str = Field(..., description="date")
    open: float = Field(..., description="opening price")
    high: float = Field(..., description="highest price")
    low: float = Field(..., description="lowest price")
    close: float = Field(..., description="closing price")
    volume: Optional[float] = Field(None, description="volume")
    amount: Optional[float] = Field(None, description="turnover amount")
    change_percent: Optional[float] = Field(None, description="price change (%)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "date": "2024-01-01",
            "open": 1785.00,
            "high": 1810.00,
            "low": 1780.00,
            "close": 1800.00,
            "volume": 10000000,
            "amount": 18000000000,
            "change_percent": 0.84
        }
    })


class ExtractItem(BaseModel):
    """single extraction result (code, name, confidence)"""

    code: Optional[str] = Field(None, description="stock code, None indicates parsing failure")
    name: Optional[str] = Field(None, description="stock name (if available)")
    confidence: str = Field("medium", description="confidence: high/medium/low")


class ExtractFromImageResponse(BaseModel):
    """image-based stock code extraction response"""

    codes: List[str] = Field(..., description="extracted stock codes (deduplicated, backward compatible)")
    items: List[ExtractItem] = Field(default_factory=list, description="detailed extraction results (code + name + confidence)")
    raw_text: Optional[str] = Field(None, description="original LLM response (for debugging)")


class StockHistoryResponse(BaseModel):
    """Stock historical quote response"""
    
    stock_code: str = Field(..., description="Stock code")
    stock_name: Optional[str] = Field(None, description="Stock name")
    period: str = Field(..., description="รอบเวลากราฟ K")
    data: List[KLineData] = Field(default_factory=list, description="K-line data list")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "Guizhou Maotai",
            "period": "daily",
            "data": []
        }
    })


class StockProfileQuoteBlock(BaseModel):
    status: StockProfileStatus
    data: Optional[StockQuote] = None
    limitations: List[str] = Field(default_factory=list)


class StockProfileHistoryBlock(BaseModel):
    status: StockProfileStatus
    period: Literal["daily"] = "daily"
    data: List[KLineData] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class StockProfileResearchData(BaseModel):
    latest_report: Optional[HistoryItem] = None
    recent_reports: List[HistoryItem] = Field(default_factory=list)
    structured_report: Optional[ResearchArtifact] = None


class StockProfileResearchBlock(BaseModel):
    status: StockProfileStatus
    data: StockProfileResearchData = Field(default_factory=StockProfileResearchData)
    limitations: List[str] = Field(default_factory=list)


class StockProfileIntelligenceBlock(BaseModel):
    status: StockProfileStatus
    items: List[IntelligenceItem] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class StockProfilePortfolioRelation(BaseModel):
    held: bool = False
    matched_markets: List[str] = Field(default_factory=list)


class StockProfilePortfolioBlock(BaseModel):
    status: StockProfileStatus
    data: StockProfilePortfolioRelation = Field(default_factory=StockProfilePortfolioRelation)
    limitations: List[str] = Field(default_factory=list)


class StockProfileMonitorData(BaseModel):
    total_rule_count: int = 0
    enabled_rule_count: int = 0
    rule_ids: List[int] = Field(default_factory=list)


class StockProfileMonitorBlock(BaseModel):
    status: StockProfileStatus
    data: StockProfileMonitorData = Field(default_factory=StockProfileMonitorData)
    limitations: List[str] = Field(default_factory=list)


class StockProfileEvidenceQuality(BaseModel):
    status: StockProfileStatus
    blocks: Dict[str, StockProfileStatus] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class StockProfileResponse(BaseModel):
    requested_code: str
    canonical_code: str
    market: Literal["cn", "hk", "us", "jp", "kr", "tw"]
    as_of: str
    quote: StockProfileQuoteBlock
    history: StockProfileHistoryBlock
    research: StockProfileResearchBlock
    intelligence: StockProfileIntelligenceBlock
    portfolio: StockProfilePortfolioBlock
    monitors: StockProfileMonitorBlock
    evidence_quality: StockProfileEvidenceQuality
