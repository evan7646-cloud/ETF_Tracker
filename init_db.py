import sqlite3
import os

def init_database():
    # 1. 自動抓取這支腳本所在的資料夾路徑 (即您的 ETF_Tracker 資料夾)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'etf_holdings.db')
    
    print(f"準備建立或連線至資料庫：{db_path}")

    # 2. 建立資料庫連線 (若檔案不存在，SQLite 會自動建立)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 3. 建立資料表 (Table) 架構
    # 使用 IF NOT EXISTS 確保重複執行不會報錯或洗掉未來存入的資料
    # Weight 使用 REAL 型態來儲存帶小數點的百分比數字
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS daily_weights (
        Date TEXT,
        ETF_Code TEXT,
        Stock_Symbol TEXT,
        Stock_Name TEXT,
        Weight REAL
    );
    """
    
    cursor.execute(create_table_sql)
    conn.commit()
    conn.close()

    print("✅ 資料庫與資料表 `daily_weights` 已成功初始化！(目前為空資料狀態)")

if __name__ == "__main__":
    init_database()