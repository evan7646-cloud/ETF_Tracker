import sqlite3
import pandas as pd
import streamlit as st
import altair as alt  # 🌟 新增 Altair 套件來客製化圖表

# ==========================================
# 1. 網頁基本設定
# ==========================================
st.set_page_config(page_title="ETF 聰明錢追蹤儀表板", layout="wide", page_icon="📈")
st.title("📊 三大主動式基金 - 籌碼流向儀表板")
st.markdown("追蹤 00981A(統一)、00991A(復華)、00980A(野村) 的集體加減碼動向。")

# ==========================================
# 2. 讀取與處理資料 (快取機制)
# ==========================================
@st.cache_data(ttl=60) # 🌟 加上 ttl=60 (60秒過期)，這樣爬蟲更新資料後，網頁過一分鐘重整就能看到了！
def load_data():
    conn = sqlite3.connect('etf_holdings.db')
    df = pd.read_sql("SELECT * FROM daily_weights", conn)
    conn.close()
    return df

df = load_data()

if df.empty:
    st.warning("⚠️ 資料庫目前沒有資料，請先執行爬蟲 crawler.py！")
else:
    available_dates = sorted(df['Date'].unique(), reverse=True)

    # ==========================================
    # 3. 側邊欄控制項
    # ==========================================
    st.sidebar.header("🗓️ 設定比較區間")
    if len(available_dates) >= 2:
        date_latest = st.sidebar.selectbox("最新日期 (T)", available_dates, index=0)
        date_prev = st.sidebar.selectbox("過去日期 (T-N)", available_dates, index=1)

        df_latest = df[df['Date'] == date_latest]
        df_prev = df[df['Date'] == date_prev]

        avg_latest = df_latest.groupby(['Stock_Symbol', 'Stock_Name'])['Weight'].mean().reset_index()
        avg_prev = df_prev.groupby(['Stock_Symbol', 'Stock_Name'])['Weight'].mean().reset_index()

        merged = pd.merge(avg_latest, avg_prev, on=['Stock_Symbol', 'Stock_Name'], suffixes=('_Latest', '_Prev'), how='outer').fillna(0)
        merged['Delta(%)'] = merged['Weight_Latest'] - merged['Weight_Prev']

        top_buy = merged[merged['Delta(%)'] > 0].sort_values(by='Delta(%)', ascending=False).head(15)
        top_sell = merged[merged['Delta(%)'] < 0].sort_values(by='Delta(%)', ascending=True).head(15)

        # ==========================================
        # 4. 視覺化圖表繪製 (使用 Altair 強制水平標籤)
        # ==========================================
        st.markdown("---")
        
        # 組合股票名稱與代號 (使用;;作為分隔符)
        top_buy = top_buy.copy()
        top_sell = top_sell.copy()
        top_buy['Label'] = top_buy['Stock_Name'] + ';;(' + top_buy['Stock_Symbol'] + ')'
        top_sell['Label'] = top_sell['Stock_Name'] + ';;(' + top_sell['Stock_Symbol'] + ')'

        st.subheader("🔥 投信集體【加碼】排行榜")
        if not top_buy.empty:
            # 繪製客製化長條圖
            chart_buy = alt.Chart(top_buy).mark_bar(color="#ff4b4b").encode(
                # 🌟 關鍵修正：labelAngle=0 強制水平，並透過 labelExpr 將名稱切割成兩行顯示
                x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')")),
                y=alt.Y('Delta(%)', title="加碼幅度 (%)"),
                # 滑鼠移過去會顯示詳細資訊
                tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('Delta(%)', format='.2f')]
            ).properties(height=400)
            
            st.altair_chart(chart_buy, use_container_width=True)
        else:
            st.info("該期間無明顯加碼標的")

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("🧊 投信集體【調節】排行榜")
        if not top_sell.empty:
            top_sell['調節幅度(%)'] = top_sell['Delta(%)'].abs()
            
            chart_sell = alt.Chart(top_sell).mark_bar(color="#00cc96").encode(
                # 🌟 關鍵修正：labelAngle=0 強制水平，並透過 labelExpr 將名稱切割成兩行顯示
                x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')")),
                y=alt.Y('調節幅度(%)', title="調節幅度 (%)"),
                tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('調節幅度(%)', format='.2f')]
            ).properties(height=400)
            
            st.altair_chart(chart_sell, use_container_width=True)
        else:
            st.info("該期間無明顯調節標的")

        # ==========================================
        # 5. 完整原始數據表格
        # ==========================================
        st.markdown("---")
        st.subheader("📋 完整成分股變動明細")
        
        display_df = merged.rename(columns={
            'Stock_Symbol': '股票代號', 
            'Stock_Name': '股票名稱',
            'Weight_Latest': f'{date_latest} 權重(%)',
            'Weight_Prev': f'{date_prev} 權重(%)',
            'Delta(%)': '兩期變動(%)'
        }).sort_values(by='兩期變動(%)', key=abs, ascending=False)
        
        st.dataframe(
            display_df.style.format({
                f'{date_latest} 權重(%)': '{:.2f}%', 
                f'{date_prev} 權重(%)': '{:.2f}%', 
                '兩期變動(%)': '{:+.2f}%'
            }),
            use_container_width=True,
            height=500
        )
    else:
        st.info("⚠️ 資料庫中需要至少累積兩天的資料，才能進行圖表比較喔！")