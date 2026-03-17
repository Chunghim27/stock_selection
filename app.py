import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.title("📊 GUVBI-X Dashboard")

# 股票池
tickers = ["NVDA", "AMD", "AVGO", "TSLA", "SMCI", "META"]

# 下載資料
def get_data(ticker):
    df = yf.download(ticker, period="2y", interval="1wk")
    df = df[['Close', 'Volume']]
    return df

# 計算 GUVBI
def compute_guvbi(df):
    df['SMA10'] = df['Close'].rolling(10).mean()
    df['STD10'] = df['Close'].rolling(10).std()
    df['Upper'] = df['SMA10'] + 2 * df['STD10']
    df['Lower'] = df['SMA10'] - 2 * df['STD10']

    df['BandPos'] = (df['Close'] - df['Lower']) / (df['Upper'] - df['Lower'])

    df['VolSMA20'] = df['Volume'].rolling(20).mean()
    df['VolSTD20'] = df['Volume'].rolling(20).std()
    df['VolZ'] = (df['Volume'] - df['VolSMA20']) / df['VolSTD20']
    df['VolFactor'] = 1 + df['VolZ'] / 4

    df['Momentum'] = df['Close'] / df['Close'].shift(4)
    df['SMA30'] = df['Close'].rolling(30).mean()
    df['TrendFactor'] = df['Close'] / df['SMA30']

    df['GUVBI3'] = (
        df['BandPos']
        * df['VolFactor']
        * df['Momentum']
        * df['TrendFactor']
        * 100
    )

    return df

# 市場判斷（QQQ）
qqq = yf.download("QQQ", period="2y", interval="1wk")
qqq['SMA200'] = qqq['Close'].rolling(40).mean()
market_bull = qqq['Close'].iloc[-1] > qqq['SMA200'].iloc[-1]

st.subheader("📈 Market Status")
if market_bull:
    st.success("Bull Market ✅ 可以交易")
else:
    st.error("No Trade ❌ 建議空手")

# 掃描股票
results = []

for t in tickers:
    df = get_data(t)
    df = compute_guvbi(df)

    latest = df.iloc[-1]

    if (
        latest['GUVBI3'] > 80 and
        latest['BandPos'] > 0.8 and
        latest['VolZ'] > 0 and
        latest['Close'] > latest['SMA30']
    ):
        results.append((t, round(latest['GUVBI3'], 2)))

# 排名
results = sorted(results, key=lambda x: x[1], reverse=True)

st.subheader("🔥 Top Signals")

if results:
    for r in results:
        st.write(f"{r[0]} → {r[1]}")
else:
    st.write("目前沒有交易機會（保持空手）")

# 建議
st.subheader("📌 Action")

if market_bull and results:
    st.success(f"BUY: {[r[0] for r in results[:3]]}")
else:
    st.warning("CASH / WAIT")
