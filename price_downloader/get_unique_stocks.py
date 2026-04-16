import sqlite3
import pandas as pd
import os
import requests
import io
import urllib3

# 關閉不安全連線的警告 (因證交所憑證問題)
urllib3.disable_warnings()

def fetch_isin_list(mode):
    """
    爬取證交所 ISIN 清單
    mode 2: 上市
    mode 4: 上櫃
    """
    url = f'https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}'
    try:
        # 由於證交所憑證問題，需加上 verify=False
        res = requests.get(url, verify=False, timeout=15)
        # 用 pandas 讀取網頁表格
        df_list = pd.read_html(io.StringIO(res.text))[0]
        
        # 網頁表格的第一欄通常包含標題與代碼，第0列是 header
        df_list.columns = df_list.iloc[0]
        df_list = df_list.iloc[1:].dropna(thresh=3) # 過濾掉分類標題等不完整列
        
        # 從「有價證券代號及名稱」欄位中抽出純代號
        # 證交所的格式是 "代號　名稱" (中間以全形 \u3000 或半形空白分隔)
        col_name = df_list.columns[0]
        symbols = df_list[col_name].astype(str).str.split('\u3000').str[0].str.strip()
        symbols = symbols.str.split(' ').str[0].str.strip()
        
        # 建立回傳用的 DataFrame
        df_res = pd.DataFrame({
            'symbol': symbols,
            'Exchange': 'TWSE' if mode == 2 else 'TPEX'
        })
        return df_res
    except Exception as e:
        print(f"爬取 strMode={mode} 時發生錯誤: {e}")
        return pd.DataFrame()

def get_unique_stocks():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, '..', 'etf_holdings.db')
    
    if not os.path.exists(db_path):
        print(f"找不到資料庫：{db_path}")
        return

    # 1. 從本地 DB 拉出不重複的名單
    conn = sqlite3.connect(db_path)
    query = """
    SELECT Stock_Symbol, MAX(Stock_Name) AS Stock_Name 
    FROM daily_weights 
    GROUP BY Stock_Symbol
    ORDER BY Stock_Symbol
    """
    df_unique = pd.read_sql(query, conn)
    conn.close()
    
    if df_unique.empty:
        print("資料庫內沒有資料！")
        return
        
    print(f"已從資料庫拉取 {len(df_unique)} 檔成分股。正前往證交所連線取得最新上市櫃清單...")
    
    # 2. 爬取 TWSE (2) 和 TPEX (4) 最新名單
    df_twse = fetch_isin_list(2)
    df_tpex = fetch_isin_list(4)
    
    # 合併最新交易所名單
    df_exchange_all = pd.concat([df_twse, df_tpex], ignore_index=True)
    # 剃除可能有空值的資料
    df_exchange_all = df_exchange_all[df_exchange_all['symbol'] != 'nan']

    # 3. 把資料庫拉出來的名單進行 Left Join 對碰
    # 必須確保比對的欄位型態皆為字串且沒有空白
    df_unique['Stock_Symbol'] = df_unique['Stock_Symbol'].astype(str).str.strip()
    df_exchange_all['symbol'] = df_exchange_all['symbol'].astype(str).str.strip()
    
    # 保留左邊 df_unique，帶入右邊的 Exchange
    merged_df = pd.merge(
        df_unique, 
        df_exchange_all, 
        left_on='Stock_Symbol', 
        right_on='symbol', 
        how='left'
    )
    
    # 4. 資料清理：刪除輔助比對的 symbol 欄位，且若爬標失敗或沒配對到，預設給 TWSE
    merged_df.drop(columns=['symbol'], inplace=True, errors='ignore')
    merged_df['Exchange'] = merged_df['Exchange'].fillna('TWSE')
    
    # 5. 直接覆寫唯一的產出表
    out_file = os.path.join(current_dir, 'unique_stocks_with_exchange.csv')
    merged_df.to_csv(out_file, index=False, encoding='utf-8-sig')
    
    print(f"✅ 更新完成！已透過網頁連線並自動配對 Exchange 屬性！")
    print(f"已將 {len(merged_df)} 筆資料匯出至：{out_file}")
    print("------- 以下為前 5 筆資料預覽 -------")
    print(merged_df.head(5))

if __name__ == "__main__":
    get_unique_stocks()
