"""AKShare ETF data source utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

try:
    import akshare as ak
except ImportError as exc:  # pragma: no cover - import failure is environment-dependent
    raise ImportError("akshare is required for ETF data fetching") from exc


Period = Literal["1m", "5m", "15m", "30m", "60m", "1d"]


class ETFDataError(ValueError):
    """Base exception for ETF data validation and upstream issues."""


class InvalidETFCodeError(ETFDataError):
    """Raised when ETF code format is invalid."""


class EmptyTimeRangeError(ETFDataError):
    """Raised when start and end do not define a valid non-empty interval."""


class UpstreamNoDataError(ETFDataError):
    """Raised when AKShare returns empty data for the query."""


@dataclass(frozen=True)
class _PeriodConfig:
    source_period: str
    resample_rule: str | None = None


_PERIOD_CONFIG: dict[str, _PeriodConfig] = {
    "1m": _PeriodConfig(source_period="1"),
    "5m": _PeriodConfig(source_period="5"),
    "15m": _PeriodConfig(source_period="15"),
    "30m": _PeriodConfig(source_period="30"),
    # AKShare ETF minute endpoint does not always provide 60m directly, normalize via 30m.
    "60m": _PeriodConfig(source_period="30", resample_rule="60min"),
    "1d": _PeriodConfig(source_period="30", resample_rule="1D"),
}


def fetch_etf_bars(
    symbol: str,
    period: Period,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    """Fetch ETF k-line data and normalize output columns.

    Returns columns:
        datetime, open, high, low, close, volume
    """
    _validate_symbol(symbol)
    start_ts, end_ts = _validate_time_range(start, end)

    if period not in _PERIOD_CONFIG:
        raise ValueError(f"Unsupported period: {period}")

    config = _PERIOD_CONFIG[period]
    raw_df = _fetch_minute_data(symbol=symbol, period=config.source_period, start=start_ts, end=end_ts)

    if config.resample_rule:
        normalized = _resample_bars(raw_df, rule=config.resample_rule)
    else:
        normalized = raw_df

    normalized = normalized.loc[(normalized["datetime"] >= start_ts) & (normalized["datetime"] <= end_ts)]

    if normalized.empty:
        raise UpstreamNoDataError("No ETF data available in the requested time range")

    normalized = normalized.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    return normalized[["datetime", "open", "high", "low", "close", "volume"]]


def _validate_symbol(symbol: str) -> None:
    if not symbol or not symbol.isdigit() or len(symbol) != 6:
        raise InvalidETFCodeError(f"Invalid ETF symbol: {symbol!r}. Expected 6-digit code")


def _validate_time_range(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if pd.isna(start_ts) or pd.isna(end_ts) or start_ts >= end_ts:
        raise EmptyTimeRangeError(f"Invalid time range: start={start!r}, end={end!r}")
    return start_ts, end_ts


def _fetch_minute_data(symbol: str, period: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    df = ak.fund_etf_hist_min_em(
        symbol=symbol,
        period=period,
        start_date=start.strftime("%Y-%m-%d %H:%M:%S"),
        end_date=end.strftime("%Y-%m-%d %H:%M:%S"),
        adjust="",
    )
    if df is None or df.empty:
        raise UpstreamNoDataError("AKShare returned no ETF data")

    rename_map = {
        "时间": "datetime",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    missing_columns = [key for key in rename_map if key not in df.columns]
    if missing_columns:
        raise UpstreamNoDataError(f"AKShare response missing columns: {missing_columns}")

    normalized = df.rename(columns=rename_map)[list(rename_map.values())].copy()
    normalized["datetime"] = pd.to_datetime(normalized["datetime"])
    for col in ["open", "high", "low", "close", "volume"]:
        normalized[col] = pd.to_numeric(normalized[col], errors="coerce")

    normalized = normalized.dropna(subset=["datetime", "open", "high", "low", "close", "volume"])
    if normalized.empty:
        raise UpstreamNoDataError("AKShare ETF data became empty after normalization")

    return normalized.sort_values("datetime").reset_index(drop=True)


def _resample_bars(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    grouped = (
        df.set_index("datetime")
        .sort_index()
        .resample(rule)
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open", "high", "low", "close"])
    )

    if grouped.empty:
        raise UpstreamNoDataError("No ETF data after period normalization")

    return grouped.reset_index()
