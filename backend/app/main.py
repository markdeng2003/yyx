from __future__ import annotations

from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Query

from app.data_source.ak_etf import (
    ETFDataError,
    UpstreamNoDataError,
    fetch_etf_bars,
)

app = FastAPI(title="ETF Volume Profile Backend")

Period = Literal["1m", "5m", "15m", "30m", "60m", "1d"]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/profile")
def get_volume_profile(
    symbol: str = Query(..., description="6-digit ETF code"),
    period: Period = Query("1d"),
    start: str = Query(..., description="Start datetime"),
    end: str = Query(..., description="End datetime"),
    bins: int = Query(24, ge=5, le=200),
    value_area_ratio: float = Query(0.7, gt=0.5, lt=1.0),
) -> dict:
    try:
        bars = fetch_etf_bars(symbol=symbol, period=period, start=start, end=end)
    except UpstreamNoDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ETFDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise HTTPException(status_code=500, detail=f"Unexpected backend error: {exc}") from exc

    prices = bars[["high", "low", "close"]].mean(axis=1).to_numpy(dtype=float)
    volumes = bars["volume"].to_numpy(dtype=float)

    if len(prices) == 0 or np.allclose(volumes.sum(), 0.0):
        raise HTTPException(status_code=404, detail="No data to build volume profile")

    low = float(np.min(bars["low"].to_numpy(dtype=float)))
    high = float(np.max(bars["high"].to_numpy(dtype=float)))
    if np.isclose(low, high):
        low -= 1e-6
        high += 1e-6

    volume_hist, edges = np.histogram(prices, bins=bins, range=(low, high), weights=volumes)
    mids = (edges[:-1] + edges[1:]) / 2.0

    poc_idx = int(np.argmax(volume_hist))

    target_volume = float(volume_hist.sum() * value_area_ratio)
    included = {poc_idx}
    current_volume = float(volume_hist[poc_idx])
    left = poc_idx - 1
    right = poc_idx + 1

    while current_volume < target_volume and (left >= 0 or right < len(volume_hist)):
        left_volume = float(volume_hist[left]) if left >= 0 else -1.0
        right_volume = float(volume_hist[right]) if right < len(volume_hist) else -1.0

        if right_volume > left_volume:
            included.add(right)
            current_volume += max(right_volume, 0.0)
            right += 1
        else:
            included.add(left)
            current_volume += max(left_volume, 0.0)
            left -= 1

    va_low_idx = min(included)
    va_high_idx = max(included)

    profile = []
    for idx, (mid, vol) in enumerate(zip(mids, volume_hist)):
        profile.append(
            {
                "bin_index": idx,
                "price_mid": float(mid),
                "volume": float(vol),
                "is_poc": idx == poc_idx,
                "is_value_area": va_low_idx <= idx <= va_high_idx,
            }
        )

    return {
        "symbol": symbol,
        "period": period,
        "start": start,
        "end": end,
        "bins": bins,
        "value_area_ratio": value_area_ratio,
        "poc": {
            "bin_index": poc_idx,
            "price_mid": float(mids[poc_idx]),
            "volume": float(volume_hist[poc_idx]),
        },
        "value_area": {
            "low_price_mid": float(mids[va_low_idx]),
            "high_price_mid": float(mids[va_high_idx]),
            "low_bin_index": int(va_low_idx),
            "high_bin_index": int(va_high_idx),
        },
        "profile": profile,
        "bars": [
            {
                "datetime": row.datetime.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
            }
            for row in bars.itertuples(index=False)
        ],
    }
