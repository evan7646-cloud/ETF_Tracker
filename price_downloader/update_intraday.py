import pandas as pd # 資料處理
import os # 檔案路徑操作
import time # 延遲控制
from datetime import datetime, timezone, timedelta # 時間處理
from tvDatafeed import TvDatafeed, Interval # TradingView 資料源

def update_intraday():
    """盤中即時更新：抓取當日最新 OHLC 並更新至各股 CSV"""
    
    # 設定路徑
    current_dir = os.path.dirname(os.path.abspath(__file__)) # 當前目錄
    hist_dir = os.path.join(current_dir, "hist_prices") # 歷史價格資料夾
    csv_path = os.path.join(current_dir, 'unique_stocks_with_exchange.csv') # 股票清單
    
    if not os.path.exists(csv_path): # 找不到股票清單就退出
        print("❌ 找不到 unique_stocks_with_exchange.csv！")
        return
    
    # 台灣時區 (UTC+8)
    tw_tz = timezone(timedelta(hours=8)) # 建立台灣時區物件
    now_tw = datetime.now(tw_tz) # 目前台灣時間
    today_str = now_tw.strftime('%Y/%m/%d') # 今天日期字串 (與 CSV 格式一致)
    
    print(f"🕐 盤中更新啟動 - 台灣時間 {now_tw.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 讀取股票清單
    df_stocks = pd.read_csv(csv_path, dtype={'Stock_Symbol': str}) # 強制代號為字串
    
    # 初始化 TradingView 連線
    tv = TvDatafeed() # 建立連線 (不需登入)
    
    # ==========================================
    # 🔍 用台積電 (2330) 探測今天是否為交易日
    # ==========================================
    try:
        probe = tv.get_hist( # 抓台積電最近 2 根日線
            symbol='2330', 
            exchange='TWSE', 
            n_bars=2, 
            interval=Interval.in_daily
        )
        if probe is None or probe.empty: # 如果連探測都失敗
            print("⚠️ 無法從 TradingView 取得探測資料，退出")
            return
        
        latest_date = probe.index[-1].strftime('%Y/%m/%d') # 最新 bar 的日期
        if latest_date != today_str: # 跟今天不同 → 今天沒開盤
            print(f"📅 今日 ({today_str}) 非交易日 (TradingView 最新資料日: {latest_date})，跳過更新")
            return
        
        print(f"✅ 確認今日 ({today_str}) 為交易日，開始更新 {len(df_stocks)} 檔股價...")
        
    except Exception as e: # 探測出錯
        print(f"❌ 探測交易日失敗: {e}")
        return
    
    # ==========================================
    # 📈 逐一更新各股當日 OHLC
    # ==========================================
    updated = 0 # 成功更新計數器
    skipped = 0 # 跳過計數器 (無歷史檔)
    failed = 0 # 失敗計數器
    
    for idx, row in df_stocks.iterrows(): # 逐筆處理
        symbol = str(row['Stock_Symbol']).strip() # 股票代號
        exchange = str(row['Exchange']).strip() # 交易所 (TWSE/TPEX)
        output_file = os.path.join(hist_dir, f"{symbol}.csv") # 對應的歷史 CSV 路徑
        
        if not os.path.exists(output_file): # 還沒有歷史檔的跳過 (可能是新股、未被 download_compare 處理過)
            skipped += 1
            continue
        
        try:
            data = tv.get_hist( # 抓該股最新 2 根日線
                symbol=symbol, 
                exchange=exchange, 
                n_bars=2, 
                interval=Interval.in_daily
            )
            
            if data is not None and not data.empty: # 有拿到資料
                latest = data.iloc[-1] # 最後一根 bar (今天的)
                latest_date_str = data.index[-1].strftime('%Y/%m/%d') # 最新 bar 日期
                
                # 讀取現有 CSV
                df_existing = pd.read_csv(output_file, dtype={'Date': str}) # 載入歷史資料
                
                # 準備新的一筆資料
                new_row = {
                    'Date': latest_date_str, # 日期
                    'Open': round(latest['open'], 1), # 開盤價
                    'High': round(latest['high'], 1), # 最高價
                    'Low': round(latest['low'], 1), # 最低價
                    'Close': round(latest['close'], 1) # 收盤價 (盤中為最新成交價)
                }
                
                if latest_date_str in df_existing['Date'].values: # 今天的 row 已存在 → 覆蓋
                    mask = df_existing['Date'] == latest_date_str # 找到對應行
                    for col in ['Open', 'High', 'Low', 'Close']: # 逐欄更新
                        df_existing.loc[mask, col] = new_row[col]
                else: # 今天的 row 不存在 → 追加
                    df_existing = pd.concat( # 接上新的一行
                        [df_existing, pd.DataFrame([new_row])], 
                        ignore_index=True
                    )
                
                df_existing.to_csv(output_file, index=False) # 寫回 CSV
                updated += 1 # 計數 +1
            
            time.sleep(0.5) # 每檔間隔 0.5 秒，避免被 TradingView 封鎖
            
        except Exception as e: # 單檔下載失敗不中斷整體流程
            print(f"❌ {symbol}: {e}")
            failed += 1
            time.sleep(1) # 出錯多等一秒再繼續
    
    # ==========================================
    # 📝 寫入更新時間戳供 Dashboard 讀取
    # ==========================================
    timestamp_file = os.path.join(current_dir, "last_price_update.txt") # 時間戳檔案路徑
    with open(timestamp_file, 'w') as f: # 覆寫時間戳
        f.write(now_tw.strftime('%Y-%m-%d %H:%M:%S'))
    
    print(f"✅ 盤中更新完成！更新 {updated} 檔 / 跳過 {skipped} 檔 / 失敗 {failed} 檔")
    print(f"⏰ 更新時間: {now_tw.strftime('%Y-%m-%d %H:%M:%S')} (台灣時間)")

if __name__ == "__main__": # 直接執行此腳本時觸發
    update_intraday()
