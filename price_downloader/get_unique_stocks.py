import sqlite3
import pandas as pd
import os

def get_unique_stocks():
    # 取得目前腳本所在目錄，再推回上一層找到 db
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, '..', 'etf_holdings.db')
    
    if not os.path.exists(db_path):
        print(f"找不到資料庫：{db_path}")
        return

    # 連線到資料庫
    conn = sqlite3.connect(db_path)
    
    # 使用 GROUP BY 和 MAX()，確保同一個代號如果對應到不同名稱，只保留一個
    query = """
    SELECT Stock_Symbol, MAX(Stock_Name) AS Stock_Name 
    FROM daily_weights 
    GROUP BY Stock_Symbol
    ORDER BY Stock_Symbol
    """
    
    # 使用 pandas 執行 SQL 並將結果放入 DataFrame
    df_unique = pd.read_sql(query, conn)
    conn.close()
    
    if df_unique.empty:
        print("資料庫內沒有資料！")
        return

    # 輸出成 CSV 檔案確認結果，utf-8-sig 可避免 Excel 開啟時中文變亂碼
    out_file = os.path.join(current_dir, 'unique_stocks.csv')
    df_unique.to_csv(out_file, index=False, encoding='utf-8-sig')
    
    print(f"成功撈取 {len(df_unique)} 檔不重複股票，已儲存至 {out_file}")

if __name__ == "__main__":
    get_unique_stocks()
