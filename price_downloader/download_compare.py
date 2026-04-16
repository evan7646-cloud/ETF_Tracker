import pandas as pd
import os
import time
from tvDatafeed import TvDatafeed, Interval 

def bulk_download_from_tv():
    # 建立一個放股價資料的專屬資料夾
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "hist_prices")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 讀取剛才合併好帶有 Exchange 欄位的清單
    csv_path = os.path.join(current_dir, 'unique_stocks_with_exchange.csv')
    if not os.path.exists(csv_path):
        print("找不到 unique_stocks_with_exchange.csv！")
        return
        
    df_stocks = pd.read_csv(csv_path)
    
    # 初始化 TradingView (未登入預設就可以用了)
    tv = TvDatafeed()                
    interval = Interval.in_daily   
    
    # 設定最大重試次數
    max_retries = 10
    
    for attempt in range(1, max_retries + 1):
        # 每次掃描還有哪些沒有下載成功
        pending_stocks = []
        for index, row in df_stocks.iterrows():
            symbol = str(row['Stock_Symbol']).strip()
            output_file = os.path.join(output_dir, f"{symbol}.csv")
            if not os.path.exists(output_file):
                pending_stocks.append((index, row, symbol, output_file))
                
        # 如果 pending_stocks 是空的，代表全部下載完了
        if not pending_stocks:
            print(f"✅ 全數資料自動抓取與儲存完畢！共跑了 {attempt-1} 回合。")
            return
            
        if attempt == 1:
            print(f"準備下載 {len(pending_stocks)} 檔股票資料...")
        else:
            print(f"🔄 發生失敗，準備進行第 {attempt} 次重試，剩餘 {len(pending_stocks)} 檔股票尚未下載成功...")
            time.sleep(3) # 重試前稍微休息一下，避免連續踩雷
            
        # 針對這回合還沒成功的部分開始下載
        for idx, row, symbol, output_file in pending_stocks:
            exchange = str(row['Exchange']).strip()
            name = row['Stock_Name']
            
            try:
                print(f"[{idx+1}/{len(df_stocks)}] (第{attempt}次嘗試) 下載中：{symbol} {name} ({exchange})...")
                # 依據資料表的 exchange 讀取
                stock_data = tv.get_hist(symbol=symbol, exchange=exchange, n_bars=7000, interval=interval)
                
                if stock_data is not None and not stock_data.empty:
                    # 整理欄位
                    df = stock_data[["open","high","low","close"]].round(1)
                    df.index = pd.to_datetime(df.index).strftime('%Y/%m/%d')
                    df.index.name = "Date"
                    df = df.rename(columns={"open":"Open", "high":"High", "low":"Low", "close":"Close"})
                    
                    # 存入 hist_prices 資料夾
                    df.to_csv(output_file)
                else:
                    # 有些股票可能剛上市或真的沒有資料，如果確定沒有就可以寫個空檔防呆，這裏我們單純提示
                    print(f"⚠️ {symbol} 找不到資料！")
                    
                # 保護機制：避免請求太快被 TradingView 封鎖 API
                time.sleep(1) 
                
            except Exception as e:
                print(f"❌ 下載 {symbol} 時發生錯誤: {e}")
                time.sleep(2) # 發生錯誤的話多延遲 2 秒再跑下一檔

    # 當跳出迴圈時代表跑滿 10 次還是有失敗
    final_fail_count = len([f for f in pending_stocks if not os.path.exists(f[3])])
    if final_fail_count > 0:
        print(f"⚠️ 已達到最大重試次數 ({max_retries})，仍有 {final_fail_count} 檔股票無法成功下載。")

if __name__ == "__main__":
    bulk_download_from_tv()
