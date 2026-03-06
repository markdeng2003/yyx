from __future__ import annotations

from datetime import datetime, time, timedelta

import altair as alt
import pandas as pd
import requests
import streamlit as st

import os


def _get_api_base_url() -> str:
    try:
        return st.secrets["API_BASE_URL"]
    except Exception:
        return os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


API_BASE_URL = _get_api_base_url()
REQUEST_TIMEOUT_SECONDS = 12

st.set_page_config(page_title="ETF Volume Profile", layout="wide")
st.title("ETF Volume Profile Demo")

now = datetime.now()
default_start = now - timedelta(days=30)

with st.sidebar:
    st.header("参数设置")
    etf_code = st.text_input("ETF 代码", value="510300").strip()
    period = st.selectbox("周期", options=["1m", "5m", "15m", "30m", "60m", "1d"], index=5)
    bins = st.number_input("分箱数", min_value=5, max_value=200, value=24, step=1)

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("开始日期", value=default_start.date())
        start_time = st.time_input("开始时间", value=time(9, 30))
    with col_end:
        end_date = st.date_input("结束日期", value=now.date())
        end_time = st.time_input("结束时间", value=time(15, 0))

    run_query = st.button("查询", type="primary")

start_dt = datetime.combine(start_date, start_time)
end_dt = datetime.combine(end_date, end_time)

st.subheader("查询参数")
st.write({
    "etf_code": etf_code,
    "period": period,
    "start": start_dt.isoformat(sep=" "),
    "end": end_dt.isoformat(sep=" "),
    "bins": int(bins),
})

if not run_query:
    st.info("请在左侧设置参数后点击“查询”。")
    st.stop()

if not etf_code:
    st.warning("请输入 ETF 代码。")
    st.stop()

if start_dt >= end_dt:
    st.warning("时间范围无效：开始时间必须早于结束时间。")
    st.stop()

params = {
    "symbol": etf_code,
    "period": period,
    "start": start_dt.isoformat(sep=" "),
    "end": end_dt.isoformat(sep=" "),
    "bins": int(bins),
}

try:
    with st.spinner("正在请求后端并计算 profile..."):
        response = requests.get(
            f"{API_BASE_URL}/profile",
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    response.raise_for_status()
except requests.Timeout:
    st.error("接口请求超时，请缩短时间范围或稍后重试。")
    st.stop()
except requests.HTTPError:
    detail = ""
    try:
        detail = response.json().get("detail", "")
    except Exception:
        pass
    st.error(f"接口错误（{response.status_code}）：{detail or response.text}")
    st.stop()
except requests.RequestException as exc:
    st.error(f"请求失败：{exc}")
    st.stop()

payload = response.json()
profile_df = pd.DataFrame(payload.get("profile", []))
bars_df = pd.DataFrame(payload.get("bars", []))

if profile_df.empty:
    st.warning("该条件下无 profile 数据。")
    st.stop()

if not bars_df.empty:
    bars_df["datetime"] = pd.to_datetime(bars_df["datetime"])

profile_df["price_mid_label"] = profile_df["price_mid"].map(lambda x: f"{x:.3f}")
profile_df["color"] = profile_df.apply(
    lambda row: "POC" if row["is_poc"] else ("Value Area" if row["is_value_area"] else "Other"),
    axis=1,
)

st.subheader("Volume Profile")

profile_chart = (
    alt.Chart(profile_df)
    .mark_bar()
    .encode(
        y=alt.Y("price_mid:Q", title="价格区间中值", sort="-x"),
        x=alt.X("volume:Q", title="成交量"),
        color=alt.Color(
            "color:N",
            title="区间",
            scale=alt.Scale(domain=["POC", "Value Area", "Other"], range=["#ef4444", "#f59e0b", "#9ca3af"]),
        ),
        tooltip=[
            alt.Tooltip("price_mid:Q", title="价格中值", format=".4f"),
            alt.Tooltip("volume:Q", title="成交量", format=",.2f"),
            alt.Tooltip("color:N", title="区间类型"),
        ],
    )
    .properties(height=500)
)

left_col, right_col = st.columns([2, 1])

with right_col:
    st.altair_chart(profile_chart, use_container_width=True)
    st.caption(
        f"POC: {payload['poc']['price_mid']:.4f} | Value Area: "
        f"[{payload['value_area']['low_price_mid']:.4f}, {payload['value_area']['high_price_mid']:.4f}]"
    )

with left_col:
    st.subheader("主图联动（K线）")
    if bars_df.empty:
        st.info("当前无 K 线数据可展示。")
    else:
        base = alt.Chart(bars_df).encode(x=alt.X("datetime:T", title="时间"))
        wick = base.mark_rule(color="#6b7280").encode(y="low:Q", y2="high:Q")
        candle = base.mark_bar(size=6).encode(
            y=alt.Y("open:Q", title="价格"),
            y2="close:Q",
            color=alt.condition("datum.close >= datum.open", alt.value("#16a34a"), alt.value("#dc2626")),
            tooltip=[
                alt.Tooltip("datetime:T", title="时间"),
                alt.Tooltip("open:Q", title="开盘", format=".4f"),
                alt.Tooltip("high:Q", title="最高", format=".4f"),
                alt.Tooltip("low:Q", title="最低", format=".4f"),
                alt.Tooltip("close:Q", title="收盘", format=".4f"),
                alt.Tooltip("volume:Q", title="成交量", format=",.2f"),
            ],
        )
        st.altair_chart((wick + candle).properties(height=500), use_container_width=True)
