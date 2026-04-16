import pandas as pd
import os

def add_exchange():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    unique_path = os.path.join(current_dir, 'unique_stocks.csv')
    list_path = os.path.join(current_dir, 'TWSE&TPEX_List.csv')
    
    if not os.path.exists(unique_path):
        print("找不到 unique_stocks.csv，請先執行 get_unique_stocks.py")
        return
        
    if not os.path.exists(list_path):
        print("找不到 TWSE&TPEX_List.csv！")
        return

    # 1. 讀取不重複名單
    df_unique = pd.read_csv(unique_path, dtype={'Stock_Symbol': str})
    
    # 2. 讀取上市櫃清單 (留意這份 CSV 可能是 cp950 或 big5 編碼)
    df_list = pd.read_csv(list_path, encoding='cp950', encoding_errors='ignore', dtype={'symbol': str})
    
    # 3. 清理與轉換格式
    df_unique['Stock_Symbol'] = df_unique['Stock_Symbol'].str.strip()
    df_list['symbol'] = df_list['symbol'].str.strip()
    
    # 建立轉換邏輯：將中文的「上市/上櫃」轉成 TradingView 吃得下得「TWSE/TPEX」
    def map_exchange(ex):
        if '上市' in str(ex): return 'TWSE'
        if '上櫃' in str(ex): return 'TPEX'
        return 'TWSE' # 預設當作上市
    
    df_list['Exchange'] = df_list['exchange'].apply(map_exchange)
    
    # 4. 合併資料 (Left Join)
    merged_df = pd.merge(
        df_unique, 
        df_list[['symbol', 'Exchange']], 
        left_on='Stock_Symbol', 
        right_on='symbol', 
        how='left'
    )
    
    # 刪除多餘的 key，填補沒對應到預設給 TWSE (許多 ETF 本身不一定在名單上，通常為 TWSE)
    merged_df.drop(columns=['symbol'], inplace=True)
    merged_df['Exchange'] = merged_df['Exchange'].fillna('TWSE')
    
    # 5. 輸出
    out_file = os.path.join(current_dir, 'unique_stocks_with_exchange.csv')
    merged_df.to_csv(out_file, index=False, encoding='utf-8-sig')
    
    print(f"✅ 核對完成！已成功加上 Exchange 欄位並儲存至：{out_file}")
    print(merged_df.head(10))

if __name__ == "__main__":
    add_exchange()
