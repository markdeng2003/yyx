import streamlit as st

st.set_page_config(page_title="ETF Volume Profile", layout="wide")

st.title("ETF Volume Profile Demo")

with st.sidebar:
    st.header("参数设置")
    etf_code = st.text_input("ETF 代码", value="510300")
    period = st.selectbox("周期", options=["1m", "5m", "15m", "30m", "60m", "1d"], index=5)
    start_date = st.date_input("开始日期")
    end_date = st.date_input("结束日期")

st.subheader("查询参数")
st.write({
    "etf_code": etf_code,
    "period": period,
    "start_date": str(start_date),
    "end_date": str(end_date),
})

st.subheader("Volume Profile 图表区域")
st.info("这里将展示 volume profile 图表（预留区域）。")
st.empty()
