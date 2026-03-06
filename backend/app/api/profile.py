"""Volume profile API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.data_source.ak_etf import ETFDataError, Period, fetch_etf_bars
from app.indicators.volume_profile import VolumeProfileError, compute_volume_profile

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile")
def get_volume_profile(
    symbol: str = Query(..., description="ETF symbol, e.g. 510300"),
    period: Period = Query("1d", description="K-line period"),
    start: str = Query(..., description="Start datetime, e.g. 2024-01-01 09:30:00"),
    end: str = Query(..., description="End datetime, e.g. 2024-12-31 15:00:00"),
    bins: int = Query(50, ge=1, le=500, description="Number of price bins"),
    price_mode: str = Query("hlc3", description="Price mapping: close or hlc3"),
) -> dict:
    try:
        bars = fetch_etf_bars(symbol=symbol, period=period, start=start, end=end)
        result = compute_volume_profile(bars, bins=bins, price_mode=price_mode)
    except (ETFDataError, VolumeProfileError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "symbol": symbol,
        "period": period,
        "start": start,
        "end": end,
        "bins": bins,
        "price_mode": result["price_mode"],
        "poc": result["poc"],
        "value_area_low": result["value_area_low"],
        "value_area_high": result["value_area_high"],
        "profile": result["profile"],
    }
