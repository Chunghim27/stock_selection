import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

st.title("📊 GUVBI-X Dashboard")

tickers = ["NVDA", "AMD", "AVGO", "TSLA", "SMCI", "META"]



def get_qqq_safe():
    try:
        df = yf.download("QQQ", period="2y", interval="1wk", progress=False)
        time.sleep(1)  # 防止被限流
        return df
    except:
        return pd.DataFrame()

qqq = get_qqq_safe()

# 🔥 關鍵：完全防炸
if qqq is None or qqq.empty or len(qqq) < 40:
    market_bull = False

else:
    qqq['SMA200'] = qqq['Close'].rolling(40).mean()

    latest_close = qqq['Close'].iloc[-1]
    latest_sma = qqq['SMA200'].iloc[-1]

    if pd.notna(latest_sma):
        market_bull = bool(latest_close > latest_sma)  # 🔥 強制轉 boolean
    else:
        market_bull = False

def get_data(ticker):
    df = yf.download(ticker, period="2y", interval="1wk", progress=False)
    if df.empty:
        return df
    return df[['Close', 'Volume']]

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

# 市場判斷（修正版）
qqq = yf.download("QQQ", period="2y", interval="1wk", progress=False)

if not qqq.empty and len(qqq) > 40:
    qqq['SMA200'] = qqq['Close'].rolling(40).mean()
    latest_close = qqq['Close'].iloc[-1]
    latest_sma = qqq['SMA200'].iloc[-1]

    if pd.notna(latest_sma):
        market_bull = latest_close > latest_sma
    else:
        market_bull = False
else:
    market_bull = False

st.subheader("📈 Market Status")

if market_bull:
    st.success("Bull Market ✅")
else:
    st.error("No Trade ❌")

results = []

for t in tickers:
    df = get_data(t)

    if df.empty or len(df) < 30:
        continue

    df = compute_guvbi(df)
    latest = df.iloc[-1]

    if (
        latest['GUVBI3'] > 80 and
        latest['BandPos'] > 0.8 and
        latest['VolZ'] > 0 and
        latest['Close'] > latest['SMA30']
    ):
        results.append((t, round(latest['GUVBI3'], 2)))

results = sorted(results, key=lambda x: x[1], reverse=True)

st.subheader("🔥 Top Signals")

if results:
    for r in results:
        st.write(f"{r[0]} → {r[1]}")
else:
    st.write("No signals (stay in cash)")

st.subheader("📌 Action")

if market_bull and results:
    st.success(f"BUY: {[r[0] for r in results[:3]]}")
else:
    st.warning("CASH / WAIT")
