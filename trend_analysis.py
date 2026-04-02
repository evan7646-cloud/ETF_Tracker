import os
import sqlite3
import pandas as pd

def classify_trend(delta):
    """根據 PDF 邏輯定義的趨勢分類器"""
    if pd.isna(delta):
        return "無資料/新增"
    
    # 四捨五入到小數點第二位以防浮點數誤差
    delta = round(delta, 2)
    
    if delta >= 1.00:
        return f"+{delta:.2f}% (大增)"
    elif delta >= 0.20:
        return f"+{delta:.2f}% (加碼)"
    elif delta >= 0.10:
        return f"+{delta:.2f}% (微增)"
    elif delta > -0.10:
        # 處理正負號顯示
        sign = "+" if delta > 0 else ""
        return f"{sign}{delta:.2f}% (持平/穩定)"
    elif delta > -0.20:
        return f"{delta:.2f}% (微降)"
    elif delta > -1.00:
        return f"{delta:.2f}% (調節)"
    else:
        return f"{delta:.2f}% (大減)"


def main():
    print("📊 ETF 三大主動基金 - 平均持股權重趨勢分析啟動...\n")
    
    # 1. 連線到資料庫
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'etf_holdings.db')
    
    if not os.path.exists(db_path):
        print("❌ 找不到資料庫檔案 etf_holdings.db")
        return

    conn = sqlite3.connect(db_path)
    
    # ==========================================
    # 🎯 2. 升級版：自訂比較區間邏輯
    # ==========================================
    # 撈出資料庫中所有的日期
    dates_df = pd.read_sql("SELECT DISTINCT Date FROM daily_weights ORDER BY Date DESC", conn)
    available_dates = dates_df['Date'].tolist()
    
    if len(available_dates) < 2:
        print("⚠️ 資料庫中的日期紀錄不足兩天，無法進行比較。請等累積兩天資料後再執行！")
        conn.close()
        return
        
    print("🗓️ 資料庫中可用的日期有：")
    for d in available_dates:
        print(f"   - {d}")
        
    print("\n💡 直接按 [Enter] 將預設比較最新的兩天，或者手動輸入日期 (格式: YYYY-MM-DD)")
    
    # 讓使用者輸入
    date_prev_input = input(f"請輸入『比較基準日 / 過去日期』 (預設 {available_dates[1]}): ").strip()
    date_latest_input = input(f"請輸入『最新交易日 / 當前日期』 (預設 {available_dates[0]}): ").strip()
    
    # 判斷使用者是否有輸入，沒有的話就用預設值
    date_prev = date_prev_input if date_prev_input else available_dates[1]
    date_latest = date_latest_input if date_latest_input else available_dates[0]
    
    # 防呆機制：確保使用者輸入的日期真的在資料庫裡
    if date_prev not in available_dates or date_latest not in available_dates:
        print("\n❌ 錯誤：您輸入的日期不在資料庫中，請重新執行並確認日期格式。")
        conn.close()
        return

    print(f"\n✅ 載入成功！比較區間設定為：{date_prev} ➡️ {date_latest}\n")
    # ==========================================
    
    # 3. 撈取這兩天的所有資料
    query = f"SELECT * FROM daily_weights WHERE Date IN ('{date_latest}', '{date_prev}')"
    df = pd.read_sql(query, conn)
    conn.close()

    # 4. 計算各股票在「當天」三大基金中的「平均權重」
    pivot_etf = df.pivot_table(index=['Date', 'Stock_Symbol', 'Stock_Name'], 
                               columns='ETF_Code', 
                               values='Weight').fillna(0)
    
    pivot_etf['Avg_Weight'] = pivot_etf.sum(axis=1) / 3
    avg_df = pivot_etf.reset_index()[['Date', 'Stock_Symbol', 'Stock_Name', 'Avg_Weight']]

    # 5. 將日期展開，進行最新日與過去日的比較 (Pivot)
    trend_df = avg_df.pivot_table(index=['Stock_Symbol', 'Stock_Name'], 
                                  columns='Date', 
                                  values='Avg_Weight').reset_index()
    
    # 將空值補 0 (代表某天沒有持股)
    trend_df = trend_df.fillna(0)
    
    # 6. 計算變化量 Delta
    trend_df['Delta'] = trend_df[date_latest] - trend_df[date_prev]
    
    # 7. 套用 PDF 的分類邏輯
    trend_df['趨勢變動'] = trend_df['Delta'].apply(classify_trend)
    
    # 格式化權重顯示
    trend_df[date_prev] = trend_df[date_prev].apply(lambda x: f"{x:.2f}%")
    trend_df[date_latest] = trend_df[date_latest].apply(lambda x: f"{x:.2f}%")

    # 8. 排序輸出 (依照絕對變動幅度由高到低)
    trend_df = trend_df.sort_values(by='Delta', ascending=False, key=abs) 
    
    # 整理最終顯示欄位
    final_report = trend_df[['Stock_Name', 'Stock_Symbol', date_prev, date_latest, '趨勢變動']]
    final_report.columns = ['股票名稱', '代號', f"{date_prev}(平均)", f"{date_latest}(最新平均)", '趨勢變動']

    # 印出結果
    print("="*80)
    print(f" 🚀 三大主動式基金平均權重趨勢對照 ({date_prev} vs {date_latest})")
    print("="*80)
    print(final_report.head(20).to_string(index=False)) 
    print("="*80)

if __name__ == "__main__":
    main()