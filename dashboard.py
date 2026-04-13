import sqlite3
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# 1. 網頁基本設定
# ==========================================
st.set_page_config(page_title="ETF 聰明錢追蹤儀表板", layout="wide", page_icon="📈")
st.title("📊 五大主動式基金：籌碼流向儀表板")
st.markdown("追蹤多檔 ETF 的集體加減碼動向，掌握投信法人核心佈局。")

# ==========================================
# 2. 讀取與處理資料 (快取機制)
# ==========================================
@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect('etf_holdings.db')
    df = pd.read_sql("SELECT * FROM daily_weights", conn)
    conn.close()
    return df

df_raw = load_data()

if df_raw.empty:
    st.warning("⚠️ 資料庫目前沒有資料，請先執行爬蟲程式！")
else:
    # 強制格式化日期
    df_raw['Date'] = pd.to_datetime(df_raw['Date'], format='mixed').dt.strftime('%Y-%m-%d')
    
    # ==========================================
    # 3. 側邊欄控制項 (日期 + ETF 勾選)
    # ==========================================
    st.sidebar.header("⚙️ 儀表板控制面板")
    
    # --- 日期選擇 ---
    all_dates = sorted(df_raw['Date'].unique(), reverse=True)
    if len(all_dates) >= 2:
        date_latest = st.sidebar.selectbox("最新日期 (T)", all_dates, index=0)
        date_prev = st.sidebar.selectbox("過去日期 (T-N)", all_dates, index=1)
    else:
        st.sidebar.info("等待資料累積中...")
        st.stop()

    st.sidebar.markdown("---")
    
    # --- ETF 勾選區 (列在日期下方) ---
    st.sidebar.subheader("🎯 篩選觀測標的")
    
    etf_names = {
        "00400A": "00400A (國泰台股動能高息)\n[4/7以後有資料]",
        "00980A": "00980A (野村臺灣智慧優選)",
        "00981A": "00981A (統一台股增長)\n[4/7以後有資料]",
        "00982A": "00982A (群益台灣精選強棒)",
        "00991A": "00991A (復華未來50)",
        "00992A": "00992A (群益台灣科技創新)"
    }
    
    # 從資料庫撈取實際存在的代號，並依照字典順序排列
    available_etf_codes = sorted(df_raw['ETF_Code'].unique())
    selected_etfs = []
    
    for code in available_etf_codes:
        # 如果 code 不在字典裡，就顯示原始代號
        label = etf_names.get(code, f"{code} (未定義名稱)")
        if st.sidebar.checkbox(label, value=True, key=f"cb_{code}"):
            selected_etfs.append(code)

    # 防呆：至少勾選一項
    if not selected_etfs:
        st.error("❌ 請至少勾選一檔 ETF！")
        st.stop()

    # ==========================================
    # 4. 資料運算與合併
    # ==========================================
    # 根據勾選過濾資料
    df_filtered = df_raw[df_raw['ETF_Code'].isin(selected_etfs)]
    
    df_latest = df_filtered[df_filtered['Date'] == date_latest]
    df_prev = df_filtered[df_filtered['Date'] == date_prev]

    # 計算平均權重 (反映集體佈局)
    avg_latest = df_latest.groupby('Stock_Symbol').agg({'Stock_Name': 'first', 'Weight': 'mean'}).reset_index()
    avg_prev = df_prev.groupby('Stock_Symbol').agg({'Stock_Name': 'first', 'Weight': 'mean'}).reset_index()

    merged = pd.merge(avg_latest, avg_prev, on='Stock_Symbol', suffixes=('_Latest', '_Prev'), how='outer')
    merged['Stock_Name'] = merged['Stock_Name_Latest'].fillna(merged['Stock_Name_Prev'])
    merged = merged.fillna(0)
    merged['Delta(%)'] = merged['Weight_Latest'] - merged['Weight_Prev']

    # --- 新增：計算各 ETF 的貢獻度 ---
    etf_detail_latest = df_latest[['Stock_Symbol', 'ETF_Code', 'Weight']]
    etf_detail_prev = df_prev[['Stock_Symbol', 'ETF_Code', 'Weight']]
    
    etf_merged = pd.merge(etf_detail_latest, etf_detail_prev, on=['Stock_Symbol', 'ETF_Code'], suffixes=('_L', '_P'), how='outer').fillna(0)
    etf_merged['ETF_Delta'] = etf_merged['Weight_L'] - etf_merged['Weight_P']
    etf_merged = etf_merged[etf_merged['ETF_Delta'].abs() > 0.001].copy() # 忽略極小浮點數誤差
    
    def format_contrib(row):
        sign = "+" if row["ETF_Delta"] > 0 else ""
        return f"{row['ETF_Code']}({sign}{row['ETF_Delta']:.2f}%)"
    
    if not etf_merged.empty:
        etf_merged['Contrib_Str'] = etf_merged.apply(format_contrib, axis=1)
        contrib_df = etf_merged.groupby('Stock_Symbol')['Contrib_Str'].apply(lambda x: ", ".join(x)).reset_index()
        contrib_df.rename(columns={'Contrib_Str': '各 ETF 異動貢獻'}, inplace=True)
    else:
        contrib_df = pd.DataFrame(columns=['Stock_Symbol', '各 ETF 異動貢獻'])

    merged = pd.merge(merged, contrib_df, on='Stock_Symbol', how='left')
    merged['各 ETF 異動貢獻'] = merged['各 ETF 異動貢獻'].fillna('-')
    # -----------------------------------

    # 篩選前 15 名變動
    top_buy = merged[merged['Delta(%)'] > 0].sort_values(by='Delta(%)', ascending=False).head(15)
    top_sell = merged[merged['Delta(%)'] < 0].sort_values(by='Delta(%)', ascending=True).head(15)

    # ==========================================
    # 5. 視覺化圖表
    # ==========================================
    st.markdown(f"### 📅 比較區間: **{date_prev}** ➔ **{date_latest}**")
    
    # 標記處理
    top_buy = top_buy.copy()
    top_sell = top_sell.copy()
    top_buy['Label'] = top_buy['Stock_Name'] + ';;(' + top_buy['Stock_Symbol'] + ')'
    top_sell['Label'] = top_sell['Stock_Name'] + ';;(' + top_sell['Stock_Symbol'] + ')'

    st.subheader("🔥 投信集體【加碼】排行榜")
    if not top_buy.empty:
        chart_buy = alt.Chart(top_buy).mark_bar(color="#ff4b4b").encode(
            x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')")),
            y=alt.Y('Delta(%)', title="加碼幅度 (%)"),
            tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('Delta(%)', format='.2f')]
        ).properties(height=400)
        st.altair_chart(chart_buy, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("🧊 投信集體【調節】排行榜")
    if not top_sell.empty:
        top_sell['調節幅度(%)'] = top_sell['Delta(%)'].abs()
        chart_sell = alt.Chart(top_sell).mark_bar(color="#00cc96").encode(
            x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')")),
            y=alt.Y('調節幅度(%)', title="調節幅度 (%)"),
            tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('調節幅度(%)', format='.2f')]
        ).properties(height=400)
        st.altair_chart(chart_sell, use_container_width=True)

    # ==========================================
    # 6. 完整明細表格 (帶顏色標示)
    # ==========================================
    st.markdown("---")
    st.subheader("📋 完整成分股變動明細")
    
    def check_status(row):
        if row['Weight_Prev'] == 0 and row['Weight_Latest'] > 0: return '🌟 新納入'
        if row['Weight_Latest'] == 0 and row['Weight_Prev'] > 0: return '❌ 已剔除'
        return '-'
            
    merged['狀態'] = merged.apply(check_status, axis=1)

    display_df = merged[['狀態', 'Stock_Symbol', 'Stock_Name', 'Weight_Latest', 'Weight_Prev', 'Delta(%)', '各 ETF 異動貢獻']].rename(columns={
        'Stock_Symbol': '股票代號', 
        'Stock_Name': '股票名稱',
        'Weight_Latest': f'{date_latest} 權重(%)',
        'Weight_Prev': f'{date_prev} 權重(%)',
        'Delta(%)': '兩期變動(%)',
        '各 ETF 異動貢獻': '異動明細 (ETF: 增減幅度)'
    }).sort_values(by='兩期變動(%)', key=abs, ascending=False)

    def highlight_rows(row):
        if row['狀態'] == '🌟 新納入': return ['background-color: rgba(231, 76, 60, 0.15)'] * len(row) 
        if row['狀態'] == '❌ 已剔除': return ['background-color: rgba(46, 204, 113, 0.15)'] * len(row)  
        return [''] * len(row)

    st.dataframe(
        display_df.style.apply(highlight_rows, axis=1).format({
            f'{date_latest} 權重(%)': '{:.2f}%', 
            f'{date_prev} 權重(%)': '{:.2f}%', 
            '兩期變動(%)': '{:+.2f}%'
        }),
        use_container_width=True,
        height=600
    )