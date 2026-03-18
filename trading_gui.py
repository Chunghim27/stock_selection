import tkinter as tk
from tkinter import ttk, messagebox
import yfinance as yf
import pandas as pd
import numpy as np
import threading
import requests
import time

# ====== Alpaca API ======
API_KEY = "你的API_KEY"
SECRET_KEY = "你的SECRET_KEY"
BASE_URL = "https://paper-api.alpaca.markets"

# ====== 參數 ======
TOP_N = 5
SLEEP = 0.3

results_df = None

# ====== 🔥 專業股票池 ======
def get_tickers():
    sources = [
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
        "https://raw.githubusercontent.com/portfolioplus/nasdaq100/master/nasdaq100.csv"
    ]

    tickers = set()

    for url in sources:
        try:
            df = pd.read_csv(url)

            if "Symbol" in df.columns:
                tickers.update(df["Symbol"].tolist())

            if "Ticker" in df.columns:
                tickers.update(df["Ticker"].tolist())

        except:
            pass

    clean = [t.replace(".", "-") for t in tickers]

    if len(clean) == 0:
        return [
            "AAPL","MSFT","NVDA","AMZN","META",
            "TSLA","GOOGL","AVGO","COST","AMD"
        ]

    return clean

# ====== 策略 ======
def get_signal(ticker):
    try:
        df = yf.download(ticker, period="2y", interval="1wk", progress=False)

        if len(df) < 35:
            return None

        df = df[['Close', 'Volume']].dropna()

        # 🔥 流動性過濾（機構級）
        if df['Volume'].iloc[-1] < 1_000_000:
            return None

        ma = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std()
        lower = ma - 2 * std
        upper = ma + 2 * std

        band = (df['Close'] - lower) / (upper - lower)

        vol = (df['Volume'] - df['Volume'].rolling(20).mean()) / df['Volume'].rolling(20).std().clip(1)
        vol_factor = 1 + vol / 4

        momentum = df['Close'] / df['Close'].shift(4)
        trend = df['Close'] / df['Close'].rolling(30).mean()

        score = band * vol_factor * momentum * trend * 100

        latest = score.iloc[-1]
        prev = score.iloc[-2]

        # 🔥 主升段起點
        if latest < 80 or latest <= prev:
            return None

        return {
            "ticker": ticker,
            "price": round(df['Close'].iloc[-1], 2),
            "score": round(latest, 2)
        }

    except:
        return None

# ====== Alpaca API ======
def get_account():
    r = requests.get(
        f"{BASE_URL}/v2/account",
        headers={
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY
        }
    )
    return r.json()

def place_order(ticker, qty):
    url = f"{BASE_URL}/v2/orders"

    data = {
        "symbol": ticker,
        "qty": qty,
        "side": "buy",
        "type": "market",
        "time_in_force": "day"
    }

    r = requests.post(url, json=data, headers={
        "APCA-API-KEY-ID": API_KEY,
        "APCA-API-SECRET-KEY": SECRET_KEY
    })

    return r.json()

# ====== 掃描 ======
def scan_market():
    global results_df

    log("🚀 開始掃描市場...")

    tickers = get_tickers()
    results = []

    for i, t in enumerate(tickers):
        log(f"掃描 {t} ({i+1}/{len(tickers)})")

        res = get_signal(t)
        if res:
            results.append(res)

        time.sleep(SLEEP)

    if not results:
        log("❌ 沒有找到訊號")
        return

    df = pd.DataFrame(results).sort_values("score", ascending=False).head(TOP_N)

    results_df = df
    update_table(df)

    log("✅ 掃描完成")

# ====== 更新表格 ======
def update_table(df):
    for row in tree.get_children():
        tree.delete(row)

    for _, r in df.iterrows():
        tree.insert("", "end", values=(r["ticker"], r["price"], r["score"]))

# ====== 自動交易 ======
def execute_trade():
    global results_df

    if results_df is None:
        messagebox.showwarning("錯誤", "請先掃描市場")
        return

    account = get_account()
    capital = float(account.get('cash', 0))

    log(f"💰 資金: {capital}")

    for _, row in results_df.iterrows():
        qty = int(capital * 0.02 / row["price"])

        if qty <= 0:
            continue

        place_order(row["ticker"], qty)
        log(f"📈 已下單 {row['ticker']} x {qty}")

    log("🎯 交易完成")

# ====== 多執行緒 ======
def run_scan():
    threading.Thread(target=scan_market).start()

def run_trade():
    threading.Thread(target=execute_trade).start()

# ====== Log ======
def log(msg):
    text.insert(tk.END, msg + "\n")
    text.see(tk.END)

# ====== GUI ======
root = tk.Tk()
root.title("🚀 GUVBI3 專業交易系統")
root.geometry("800x600")

frame = tk.Frame(root)
frame.pack(pady=10)

scan_btn = tk.Button(frame, text="掃描市場", command=run_scan, width=15)
scan_btn.grid(row=0, column=0, padx=10)

trade_btn = tk.Button(frame, text="自動交易", command=run_trade, width=15)
trade_btn.grid(row=0, column=1, padx=10)

# 表格
tree = ttk.Treeview(root, columns=("Ticker", "Price", "Score"), show="headings")
tree.heading("Ticker", text="Ticker")
tree.heading("Price", text="價格")
tree.heading("Score", text="分數")
tree.pack(fill="both", expand=True)

# Log
text = tk.Text(root, height=12)
text.pack(fill="both")

root.mainloop()