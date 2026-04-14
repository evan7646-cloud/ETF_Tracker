import pandas as pd
import sqlite3
import os

db_path = 'etf_holdings.db'
csv_path = 'hist_holdings_all.csv'

def import_data():
    if not os.path.exists(csv_path):
        print(f"找不到檔案：{csv_path}")
        return

    # 嘗試不同的編碼讀取
    for enc in ['utf-8', 'big5', 'utf-8-sig', 'cp950']:
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            print(f"成功使用 {enc} 編碼讀取 CSV")
            break
        except UnicodeDecodeError:
            continue
    else:
        print("無法以任何已知編碼讀取 CSV")
        return

    # 清理資料：統一日期格式為 YYYY-MM-DD (配合 crawler.py 的格式)
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
    
    # 確保資料型態乾淨
    df['Stock_Symbol'] = df['Stock_Symbol'].astype(str).str.strip()
    df['ETF_Code'] = df['ETF_Code'].astype(str).str.strip()
    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')

    # 連接資料庫並寫入
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 寫入前先刪除資料庫中當天該 ETF 的資料，避免重複
    for date_val in df['Date'].unique():
        for etf_val in df['ETF_Code'].unique():
            cur.execute("DELETE FROM daily_weights WHERE Date = ? AND ETF_Code = ?", (str(date_val), str(etf_val)))
    conn.commit()

    df.to_sql('daily_weights', conn, if_exists='append', index=False)
    conn.close()

    print(f"✅ 成功將 {len(df)} 筆資料匯入 {db_path}！")

if __name__ == "__main__":
    import_data()
