import tkinter as tk
from tkinter import ttk, messagebox
import yfinance as yf
import pandas as pd
import numpy as np
import threading
import requests
import time

# ====== Alpaca API （請自行填入真實金鑰） ======
API_KEY = "你的API_KEY"
SECRET_KEY = "你的SECRET_KEY"
BASE_URL = "https://paper-api.alpaca.markets"

# ====== 參數 ======
TOP_N = 5           # 顯示前幾名
SLEEP = 0.3         # 每檔股票間隔秒數，避免被 yfinance 封鎖
results_df = None

# ====== 專業股票池 ======
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
    clean = [t.replace(".", "-") for t in tickers if t]  # 移除空值並處理 . → -
    if len(clean) == 0:
        return ["AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","AVGO","COST","AMD"]
    return sorted(clean)  # 排序讓每次跑的順序一致

# ====== 計算 GUVBI3 分數 ======
def get_signal(ticker):
    try:
        df = yf.download(ticker, period="2y", interval="1wk", progress=False)
        if len(df) < 35:
            return None
        
        df = df[['Close', 'Volume']].dropna()
        
        # 流動性過濾（可調整）
        if df['Volume'].iloc[-1] < 1_000_000:
            return None
        
        # 布林帶
        ma = df['Close'].rolling(20).mean()
        std = df['Close'].rolling(20).std()
        lower = ma - 2 * std
        upper = ma + 2 * std
        band = (df['Close'] - lower) / (upper - lower).replace(0, np.nan)  # 避免除零
        
        # 量能因子
        vol_ma = df['Volume'].rolling(20).mean()
        vol_std = df['Volume'].rolling(20).std()
        vol_z = (df['Volume'] - vol_ma) / vol_std.clip(1)
        vol_factor = 1 + vol_z / 4
        
        # 動能因子
        momentum = df['Close'] / df['Close'].shift(4).clip(0.000001)
        
        # 趨勢因子
        trend = df['Close'] / df['Close'].rolling(30).mean().clip(0.000001)
        
        # GUVBI3 分數
        score = band * vol_factor * momentum * trend * 100
        latest = score.iloc[-1]
        prev = score.iloc[-2] if len(score) > 1 else latest
        
        # 主升段起點條件（可調整）
        if pd.isna(latest) or latest < 80 or latest <= prev:
            return None
        
        return {
            "ticker": ticker,
            "score": round(latest, 2),
            "price": round(df['Close'].iloc[-1], 2)
        }
    
    except Exception as e:
        # print(f"{ticker} 錯誤: {e}")  # 除錯時可開啟
        return None

# ====== Alpaca 帳戶查詢 ======
def get_account():
    try:
        r = requests.get(
            f"{BASE_URL}/v2/account",
            headers={
                "APCA-API-KEY-ID": API_KEY,
                "APCA-API-SECRET-KEY": SECRET_KEY
            }
        )
        return r.json()
    except:
        return {"cash": "0"}

# ====== 下單函數 ======
def place_order(ticker, qty):
    url = f"{BASE_URL}/v2/orders"
    data = {
        "symbol": ticker,
        "qty": str(qty),
        "side": "buy",
        "type": "market",
        "time_in_force": "day"
    }
    try:
        r = requests.post(url, json=data, headers={
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": SECRET_KEY
        })
        return r.json()
    except:
        return {"error": "下單失敗"}

# ====== 掃描市場（由高到低排列） ======
def scan_market():
    global results_df
    log("🚀 開始掃描市場...")
    tickers = get_tickers()
    log(f"總共 {len(tickers)} 檔股票待掃描")
    
    results = []
    for i, t in enumerate(tickers):
        log(f"[{i+1}/{len(tickers)}] 處理 {t}")
        res = get_signal(t)
        if res:
            results.append(res)
        time.sleep(SLEEP)
    
    if not results:
        log("❌ 沒有找到符合條件的訊號")
        return
    
    # 按照 GUVBI3 分數由高到低排序
    df = pd.DataFrame(results)
    df = df.sort_values("score", ascending=False).head(TOP_N)
    results_df = df
    
    update_table(df)
    log(f"✅ 掃描完成！找到 {len(results)} 檔符合訊號，前 {TOP_N} 名如下：")
    log(df.to_string(index=False))

# ====== 更新表格（分數優先） ======
def update_table(df):
    for row in tree.get_children():
        tree.delete(row)
    for _, r in df.iterrows():
        tree.insert("", "end", values=(r["ticker"], r["score"], r["price"]))

# ====== 自動交易 ======
def execute_trade():
    global results_df
    if results_df is None or results_df.empty:
        messagebox.showwarning("錯誤", "請先掃描市場並取得結果")
        return
    
    account = get_account()
    cash = float(account.get('cash', 0))
    log(f"💰 可用資金: ${cash:,.2f}")
    
    for _, row in results_df.iterrows():
        if cash <= 0:
            break
        qty = int(cash * 0.02 / row["price"])  # 每檔最多用 2% 資金
        if qty <= 0:
            continue
        result = place_order(row["ticker"], qty)
        if "id" in result:
            log(f"📈 已下單 {row['ticker']} x {qty} @ ${row['price']:.2f}")
            cash -= qty * row["price"]
        else:
            log(f"❌ {row['ticker']} 下單失敗：{result.get('error', '未知錯誤')}")
    
    log("🎯 本次交易完成")

# ====== 多執行緒啟動 ======
def run_scan():
    threading.Thread(target=scan_market, daemon=True).start()

def run_trade():
    threading.Thread(target=execute_trade, daemon=True).start()

# ====== Log 輸出 ======
def log(msg):
    text.insert(tk.END, msg + "\n")
    text.see(tk.END)

# ====== GUI 介面 ======
root = tk.Tk()
root.title("🚀 GUVBI3 專業掃描系統（分數由高到低）")
root.geometry("800x600")
root.configure(bg="#f0f0f0")

frame = tk.Frame(root, bg="#f0f0f0")
frame.pack(pady=10)

scan_btn = tk.Button(frame, text="開始掃描", command=run_scan, width=15, bg="#4CAF50", fg="white")
scan_btn.grid(row=0, column=0, padx=10)

trade_btn = tk.Button(frame, text="執行交易", command=run_trade, width=15, bg="#2196F3", fg="white")
trade_btn.grid(row=0, column=1, padx=10)

# 表格（分數優先）
tree = ttk.Treeview(root, columns=("Ticker", "Score", "Price"), show="headings")
tree.heading("Ticker", text="股票代碼")
tree.heading("Score", text="GUVBI3 分數")
tree.heading("Price", text="最新價格")
tree.column("Ticker", width=120, anchor="center")
tree.column("Score", width=120, anchor="center")
tree.column("Price", width=120, anchor="center")
tree.pack(fill="both", expand=True, padx=10, pady=10)

# Log 區
text = tk.Text(root, height=12, bg="#1e1e1e", fg="#00ff41", font=("Consolas", 10))
text.pack(fill="both", padx=10, pady=5)

root.mainloop()