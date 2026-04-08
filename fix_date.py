import sqlite3
import pandas as pd

def fix_database_dates():
    db_path = 'etf_holdings.db'
    table_name = 'daily_weights'
    
    print("⏳ 準備連線並清洗資料庫日期...")
    conn = sqlite3.connect(db_path)
    
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        
        # 1. 魔法轉換：統一所有日期格式
        df['Date'] = pd.to_datetime(df['Date'], format='mixed').dt.strftime('%Y-%m-%d')
        
        # 2. 殺手鐧：剔除因為日期統一而出現的重複資料
        before_count = len(df)
        df = df.drop_duplicates(subset=['Date', 'ETF_Code', 'Stock_Symbol'], keep='last')
        after_count = len(df)
        
        # 3. 寫回資料庫覆蓋舊表
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        
        # 4. 重新建立嚴格的防呆索引
        conn.execute(f'''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_record 
            ON {table_name} (Date, ETF_Code, Stock_Symbol)
        ''')
        
        print(f"🧹 成功清理了 {before_count - after_count} 筆隱藏的重複資料。")
        print(f"✅ 成功統一了 {len(df)} 筆資料的日期格式，資料庫現在非常乾淨！")
        
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_database_dates()