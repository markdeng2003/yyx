"""Volume profile indicator utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


class VolumeProfileError(ValueError):
    """Raised when volume profile input is invalid."""


def compute_volume_profile(df: pd.DataFrame, bins: int = 50, price_mode: str = "hlc3") -> dict:
    """Compute a binned volume profile and key levels.

    Args:
        df: DataFrame containing at least OHLCV columns.
        bins: Number of equal-width price bins.
        price_mode: Price mapping mode. Supported: ``close`` and ``hlc3``.

    Returns:
        Dict containing profile detail rows and key levels:
            price_bin_low, price_bin_high, volume, poc,
            value_area_low, value_area_high.
    """
    if df is None or df.empty:
        raise VolumeProfileError("Input dataframe is empty")
    if not isinstance(bins, int) or bins <= 0:
        raise VolumeProfileError("bins must be a positive integer")

    required = {"high", "low", "close", "volume"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise VolumeProfileError(f"Missing required columns: {missing}")

    if price_mode == "close":
        mapped_price = pd.to_numeric(df["close"], errors="coerce")
    elif price_mode == "hlc3":
        mapped_price = (
            pd.to_numeric(df["high"], errors="coerce")
            + pd.to_numeric(df["low"], errors="coerce")
            + pd.to_numeric(df["close"], errors="coerce")
        ) / 3.0
    else:
        raise VolumeProfileError(f"Unsupported price_mode: {price_mode!r}")

    volume = pd.to_numeric(df["volume"], errors="coerce")
    frame = pd.DataFrame({"price": mapped_price, "volume": volume}).dropna()
    frame = frame[frame["volume"] >= 0]
    if frame.empty:
        raise VolumeProfileError("No valid price/volume rows after normalization")

    price_min = float(frame["price"].min())
    price_max = float(frame["price"].max())

    if np.isclose(price_min, price_max):
        eps = max(abs(price_min) * 1e-6, 1e-6)
        edges = np.array([price_min - eps, price_max + eps], dtype=float)
    else:
        edges = np.linspace(price_min, price_max, num=bins + 1, dtype=float)

    bucket = pd.cut(frame["price"], bins=edges, include_lowest=True, right=False)
    grouped = frame.groupby(bucket, observed=False)["volume"].sum().reset_index()

    profile = pd.DataFrame(
        {
            "price_bin_low": [interval.left for interval in grouped["price"]],
            "price_bin_high": [interval.right for interval in grouped["price"]],
            "volume": grouped["volume"].astype(float),
        }
    )

    profile = profile[profile["volume"] > 0].reset_index(drop=True)
    if profile.empty:
        raise VolumeProfileError("All binned volumes are zero")

    poc_idx = int(profile["volume"].idxmax())
    poc = float((profile.loc[poc_idx, "price_bin_low"] + profile.loc[poc_idx, "price_bin_high"]) / 2.0)

    total_volume = float(profile["volume"].sum())
    target_volume = 0.7 * total_volume
    included = {poc_idx}
    cumulative = float(profile.loc[poc_idx, "volume"])
    left = poc_idx - 1
    right = poc_idx + 1

    while cumulative < target_volume and (left >= 0 or right < len(profile)):
        left_volume = float(profile.loc[left, "volume"]) if left >= 0 else -1.0
        right_volume = float(profile.loc[right, "volume"]) if right < len(profile) else -1.0

        if right_volume > left_volume:
            included.add(right)
            cumulative += right_volume
            right += 1
        else:
            if left >= 0:
                included.add(left)
                cumulative += left_volume
                left -= 1
            elif right < len(profile):
                included.add(right)
                cumulative += right_volume
                right += 1

    va_slice = profile.loc[sorted(included)]
    value_area_low = float(va_slice["price_bin_low"].min())
    value_area_high = float(va_slice["price_bin_high"].max())

    return {
        "price_mode": price_mode,
        "bins": bins,
        "profile": profile.to_dict(orient="records"),
        "poc": poc,
        "value_area_low": value_area_low,
        "value_area_high": value_area_high,
    }
