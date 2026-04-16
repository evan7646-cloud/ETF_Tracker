import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
import base64
import os

# ==========================================
# 1. 網頁基本設定與自訂標題
# ==========================================
st.set_page_config(page_title="主動式ETF追蹤儀表板", layout="wide", page_icon="📈")

# 動態將 Logo 轉為 Base64 顯示以達成同行對齊
logo_base64 = ""
if os.path.exists("logo.png"):
    with open("logo.png", "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode()

title_html = f"""
<style>
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{visibility: hidden;}}
</style>
<div style="margin-bottom: 20px;">
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
        <img src="data:image/png;base64,{logo_base64}" width="32" style="object-fit: contain;">
        <span style="color: #CD002A; font-weight: 900; font-size: 28px;">國票期貨法人部製作</span>
    </div>
    <h2 style="margin: 0; font-size: 28px;">📊 主動式ETF：籌碼流向儀表板</h2>
</div>
"""
st.markdown(title_html, unsafe_allow_html=True)

st.markdown("""
💡 **本儀表板提供四大核心功能：**
1. 🏆 **持股變動綜合排行**：投信資金集中押注或大幅撤出的熱門標的。
2. 📝 **成分股調倉明細單**：列出各支 ETF 對特定股票的加減碼操作 (包含前次與最新權重狀態)。
3. 📈 **歷史 K 線與權重對照圖**：將股價走勢結合階梯式的持股權重變動。
4. 🔲 **持股熱力圖**：顏色代表漲跌停，格子大小代表持股權重。
""")

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
    # 3. 主畫面控制項 (日期 + ETF 勾選)
    # ==========================================
    with st.expander("⚙️ 打開控制面板 (選擇比較日期與過濾 ETF)", expanded=True):
        st.subheader("📅 日期與區間設定")
        date_col1, date_col2 = st.columns(2)
        
        # --- 日期選擇 (日曆模式) ---
        all_dates = sorted(df_raw['Date'].unique(), reverse=True)
        if len(all_dates) >= 2:
            min_date = pd.to_datetime(all_dates[-1]).date()
            max_date = pd.to_datetime(all_dates[0]).date()
            
            default_latest = max_date
            default_prev = pd.to_datetime(all_dates[1]).date()
            
            with date_col1:
                date_prev_obj = st.date_input("🗓️ 過去日期 (T-N)", value=default_prev, min_value=min_date, max_value=max_date, format="YYYY-MM-DD")
            with date_col2:
                date_latest_obj = st.date_input("🗓️ 最新日期 (T)", value=default_latest, min_value=min_date, max_value=max_date, format="YYYY-MM-DD")
            
            date_latest = date_latest_obj.strftime('%Y-%m-%d')
            date_prev = date_prev_obj.strftime('%Y-%m-%d')
            
            # 防呆：避免使用者選到假日
            if date_latest not in all_dates:
                st.warning(f"⚠️ {date_latest} 沒有基金交易紀錄 (可能是假日)，請重新選擇日期！")
                st.stop()
            if date_prev not in all_dates:
                st.warning(f"⚠️ {date_prev} 沒有基金交易紀錄 (可能是假日)，請重新選擇日期！")
                st.stop()
        else:
            st.info("等待資料累積中...")
            st.stop()

        # 顯示下載失敗警示
        import os
        missing_path = os.path.join("price_downloader", "missing_stocks.txt")
        if os.path.exists(missing_path):
            with open(missing_path, "r", encoding="utf-8") as f:
                missing_syms = [s.strip() for s in f.readlines() if s.strip()]
            if missing_syms:
                st.error(f"⚠️ **無股價資料之成分股：**\n\n{', '.join(missing_syms)}\n\n*(資料來源無法對應)*")

        st.markdown("---")

        # --- ETF 勾選區 ---
        st.subheader("🎯 篩選觀測標的")
        etf_names = {
            "00400A": "00400A (國泰台股動能高息)",
            "00980A": "00980A (野村臺灣智慧優選)",
            "00981A": "00981A (統一台股增長)",
            "00982A": "00982A (群益台灣精選強棒)",
            "00991A": "00991A (復華未來50)",
            "00992A": "00992A (群益台灣科技創新)"
        }
        available_etf_codes = sorted(df_raw['ETF_Code'].unique())
        selected_etfs = []

        if "select_all" not in st.session_state:
            st.session_state.select_all = True

        def toggle_all():
            for code in available_etf_codes:
                st.session_state[f"cb_{code}"] = st.session_state.select_all

        # 第一排：全選
        st.checkbox("✅ 全選所有 ETF", key="select_all", on_change=toggle_all)
        
        # 第二與第三排：各 3 檔 (共 6 檔)
        row1_cols = st.columns(3)
        row2_cols = st.columns(3)
        
        for idx, code in enumerate(available_etf_codes):
            label = etf_names.get(code, f"{code} (未定義名稱)")
            
            if f"cb_{code}" not in st.session_state:
                st.session_state[f"cb_{code}"] = st.session_state.select_all
                
            # 決定應該放在哪一欄
            target_col = row1_cols[idx] if idx < 3 else row2_cols[idx - 3]
            
            if target_col.checkbox(label, key=f"cb_{code}"):
                selected_etfs.append(code)
                
        with st.popover("💡 點此查看 ETF 起始日參考"):
            st.markdown("""
            | ETF 代號 | 最早資料日期 |
            | :--- | :--- |
            | **00980A** | 2025-05-02 |
            | **00982A** | 2025-05-21 |
            | **00981A** | 2025-05-26 |
            | **00991A** | 2025-12-10 |
            | **00992A** | 2025-12-29 |
            | **00400A** | 2026-04-02 |
            """)

    # 防呆：至少勾選一項
    if not selected_etfs:
        st.error("❌ 請至少勾選一檔 ETF！")
        st.stop()

    # 自動檢查是否踩到 ETF 創立前區間
    warning_msgs = []
    for code in selected_etfs:
        min_date = df_raw[df_raw['ETF_Code'] == code]['Date'].min()
        if min_date > date_prev:
            name_label = etf_names.get(code, code).split(' ')[0] # 擷取代號
            warning_msgs.append(f"- **{name_label}** (最舊紀錄：{min_date})")
            
    if warning_msgs:
        st.warning(f"⚠️ **注意：您所選的比較基準日 (`{date_prev}`) 早於以下 ETF 的創立/建檔日期：**\n\n" + "\n".join(warning_msgs) + "\n\n*(這些 ETF 將呈現從 0% 建倉至滿水位的異常巨大增幅，敬請留意！)*")
    # ==========================================
    # 4. 資料運算與合併
    # ==========================================
    # 根據勾選過濾資料
    df_filtered = df_raw[df_raw['ETF_Code'].isin(selected_etfs)]
    
    df_latest = df_filtered[df_filtered['Date'] == date_latest]
    df_prev = df_filtered[df_filtered['Date'] == date_prev]

    # 計算總和權重 (反映整體資金增減)
    tot_latest = df_latest.groupby('Stock_Symbol').agg({'Stock_Name': 'first', 'Weight': 'sum'}).reset_index()
    tot_prev = df_prev.groupby('Stock_Symbol').agg({'Stock_Name': 'first', 'Weight': 'sum'}).reset_index()

    merged = pd.merge(tot_latest, tot_prev, on='Stock_Symbol', suffixes=('_Latest', '_Prev'), how='outer')
    merged['Stock_Name'] = merged['Stock_Name_Latest'].fillna(merged['Stock_Name_Prev'])
    merged = merged.fillna(0)
    merged['Delta(%)'] = merged['Weight_Latest'] - merged['Weight_Prev']

    # --- 新增：計算各 ETF 的貢獻度 ---
    etf_detail_latest = df_latest[['Stock_Symbol', 'ETF_Code', 'Weight']]
    etf_detail_prev = df_prev[['Stock_Symbol', 'ETF_Code', 'Weight']]
    
    etf_merged = pd.merge(etf_detail_latest, etf_detail_prev, on=['Stock_Symbol', 'ETF_Code'], suffixes=('_L', '_P'), how='outer').fillna(0)
    etf_merged['ETF_Delta'] = etf_merged['Weight_L'] - etf_merged['Weight_P']
    etf_merged = etf_merged[etf_merged['ETF_Delta'].abs() > 0.001].copy() # 忽略極小浮點數誤差
    
    def format_up(row):
        return f"{row['ETF_Code']}(+{row['ETF_Delta']:.2f}%)" if row["ETF_Delta"] > 0 else None
        
    def format_down(row):
        return f"{row['ETF_Code']}({row['ETF_Delta']:.2f}%)" if row["ETF_Delta"] < 0 else None
    
    if not etf_merged.empty:
        etf_merged['Up_Str'] = etf_merged.apply(format_up, axis=1)
        etf_merged['Down_Str'] = etf_merged.apply(format_down, axis=1)
        
        up_df = etf_merged.dropna(subset=['Up_Str']).groupby('Stock_Symbol')['Up_Str'].apply(lambda x: ", ".join(x)).reset_index()
        down_df = etf_merged.dropna(subset=['Down_Str']).groupby('Stock_Symbol')['Down_Str'].apply(lambda x: ", ".join(x)).reset_index()
        
        contrib_df = pd.merge(up_df, down_df, on='Stock_Symbol', how='outer')
        contrib_df.rename(columns={'Up_Str': '▲ 加碼 ETF', 'Down_Str': '▼ 調節 ETF'}, inplace=True)
    else:
        contrib_df = pd.DataFrame(columns=['Stock_Symbol', '▲ 加碼 ETF', '▼ 調節 ETF'])

    merged = pd.merge(merged, contrib_df, on='Stock_Symbol', how='left')
    merged['▲ 加碼 ETF'] = merged['▲ 加碼 ETF'].fillna('-')
    merged['▼ 調節 ETF'] = merged['▼ 調節 ETF'].fillna('-')
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

    st.markdown("<h3 style='font-size: 26px;'>🔥 投信集體【加碼】排行榜</h3>", unsafe_allow_html=True)
    if not top_buy.empty:
        chart_buy = alt.Chart(top_buy).mark_bar(color="#ff4b4b").encode(
            x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')", labelFontSize=16, titleFontSize=14)),
            y=alt.Y('Delta(%)', title="加碼幅度 (%)"),
            tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('Delta(%)', format='.2f')]
        ).properties(height=400)
        st.altair_chart(chart_buy, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("<h3 style='font-size: 26px;'>🧊 投信集體【調節】排行榜</h3>", unsafe_allow_html=True)
    if not top_sell.empty:
        top_sell['調節幅度(%)'] = top_sell['Delta(%)'].abs()
        chart_sell = alt.Chart(top_sell).mark_bar(color="#00cc96").encode(
            x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')", labelFontSize=16, titleFontSize=14)),
            y=alt.Y('調節幅度(%)', title="調節幅度 (%)"),
            tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('調節幅度(%)', format='.2f')]
        ).properties(height=400)
        st.altair_chart(chart_sell, use_container_width=True)

    # ==========================================
    # 6. 完整明細表格 (帶顏色標示)
    # ==========================================
    st.markdown("---")
    st.markdown("<h3 style='font-size: 28px;'>📋 完整成分股變動明細</h3>", unsafe_allow_html=True)
    
    def check_status(row):
        if row['Weight_Prev'] == 0 and row['Weight_Latest'] > 0: return '🌟 新納入'
        if row['Weight_Latest'] == 0 and row['Weight_Prev'] > 0: return '❌ 已剔除'
        return '-'
            
    merged['狀態'] = merged.apply(check_status, axis=1)

    display_df = merged[['狀態', 'Stock_Symbol', 'Stock_Name', 'Weight_Latest', 'Weight_Prev', 'Delta(%)', '▲ 加碼 ETF', '▼ 調節 ETF']].rename(columns={
        'Stock_Symbol': '股票代號', 
        'Stock_Name': '股票名稱',
        'Weight_Latest': f'{date_latest} 總權重(%)',
        'Weight_Prev': f'{date_prev} 總權重(%)',
        'Delta(%)': '兩期總變動(%)'
    }).sort_values(by='兩期總變動(%)', key=abs, ascending=False)

    def highlight_rows(row):
        if row['狀態'] == '🌟 新納入': return ['background-color: rgba(231, 76, 60, 0.15)'] * len(row) 
        if row['狀態'] == '❌ 已剔除': return ['background-color: rgba(46, 204, 113, 0.15)'] * len(row)  
        return [''] * len(row)

    def color_text(val, color):
        return f'color: {color};' if val != '-' else ''

    # 恢復互動式表格並使用欄位文字上色
    styled_df = display_df.style.apply(highlight_rows, axis=1)\
        .map(lambda x: color_text(x, '#ff4b4b'), subset=['▲ 加碼 ETF'])\
        .map(lambda x: color_text(x, '#00cc96'), subset=['▼ 調節 ETF'])\
        .format({
            f'{date_latest} 總權重(%)': '{:.2f}%', 
            f'{date_prev} 總權重(%)': '{:.2f}%', 
            '兩期總變動(%)': '{:+.2f}%'
        })
        
    st.markdown("🎯 **操作提示**：點擊表格最左側的方塊 (或整列)，即可在最下方展開！")
    selection = st.dataframe(
        styled_df,
        use_container_width=True,
        height=600,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "狀態": st.column_config.TextColumn(width="small"),
            "股票代號": st.column_config.TextColumn(width="small"),
            "股票名稱": st.column_config.TextColumn(width="small"),
            f"{date_latest} 總權重(%)": st.column_config.TextColumn(width="small"),
            f"{date_prev} 總權重(%)": st.column_config.TextColumn(width="small"),
            "兩期總變動(%)": st.column_config.TextColumn(width="small"),
            "▲ 加碼 ETF": st.column_config.TextColumn(width="medium"),
            "▼ 調節 ETF": st.column_config.TextColumn(width="medium")
        }
    )

    # ==========================================
    # 5. 個股每日動態深度追蹤 (點擊展開)
    # ==========================================
    if selection and selection.selection.rows:
        row_idx = selection.selection.rows[0]
        sel_symbol = display_df.iloc[row_idx]['股票代號']
        sel_name = display_df.iloc[row_idx]['股票名稱']
        
        st.markdown(f"### 🔍 {sel_name} ({sel_symbol}) - 區間走勢與權重動態")
        
        import os
        import pandas as pd
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        import plotly.express as px

        csv_path = os.path.join("price_downloader", "hist_prices", f"{sel_symbol}.csv")
        has_kline = False
        df_range = pd.DataFrame()
        
        if os.path.exists(csv_path):
            df_price = pd.read_csv(csv_path)
            df_price['Date'] = pd.to_datetime(df_price['Date'])
            d1 = pd.to_datetime(date_prev)
            d2 = pd.to_datetime(date_latest)
            df_range = df_price[(df_price['Date'] >= d1) & (df_price['Date'] <= d2)].copy()
            if not df_range.empty:
                has_kline = True

        df_stock = df_filtered[
            (df_filtered['Stock_Symbol'] == sel_symbol) & 
            (df_filtered['Date'] >= date_prev) & 
            (df_filtered['Date'] <= date_latest)
        ].copy()
        
        if not df_stock.empty:
            df_stock['Date'] = pd.to_datetime(df_stock['Date'])
            if has_kline:
                # 建立上下聯動的雙視窗 (共用 X 軸)
                fig = make_subplots(
                    rows=2, cols=1, 
                    shared_xaxes=True, 
                    vertical_spacing=0.08,
                    row_heights=[0.5, 0.5]
                )
                
                # 繪製上面的 K 線圖
                fig.add_trace(go.Candlestick(
                    x=df_range['Date'],
                    open=df_range['Open'],
                    high=df_range['High'],
                    low=df_range['Low'],
                    close=df_range['Close'],
                    name="K線走勢",
                    increasing_line_color='#ef313d', increasing_fillcolor='#ef313d', 
                    decreasing_line_color='#36a555', decreasing_fillcolor='#36a555'
                ), row=1, col=1)
                
                # 繪製下面的各 ETF 折線圖
                etf_codes = df_stock['ETF_Code'].unique()
                color_seq = px.colors.qualitative.Plotly
                for i, code in enumerate(etf_codes):
                    sub_df = df_stock[df_stock['ETF_Code'] == code].sort_values('Date')
                    fig.add_trace(go.Scatter(
                        x=sub_df['Date'],
                        y=sub_df['Weight'],
                        mode='lines+markers',
                        line_shape='hv',
                        name=code,
                        line=dict(width=3, color=color_seq[i % len(color_seq)]),
                        hovertemplate='ETF: ' + code + '<br>權重: %{y:.2f}%<extra></extra>'
                    ), row=2, col=1)
                
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    height=750,
                    margin=dict(t=30, l=10, r=10, b=10),
                    hovermode="x unified", # 開啟全局十字鼠標垂直連動線 (最重要的一步！)
                    legend_title="圖例標籤"
                )
                fig.update_yaxes(title_text="股價 (TWD)", row=1, col=1)
                fig.update_yaxes(title_text="權重 (%)", row=2, col=1)
                
                # 強制使用類別型態，消去所有假日/無交易日的斷層點，並設定刻度數量避免太密集
                fig.update_xaxes(type='category', categoryorder='category ascending', nticks=15)
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                # 若無 K 線僅單獨顯示折線
                fig = go.Figure()
                etf_codes = df_stock['ETF_Code'].unique()
                color_seq = px.colors.qualitative.Plotly
                for i, code in enumerate(etf_codes):
                    sub_df = df_stock[df_stock['ETF_Code'] == code].sort_values('Date')
                    fig.add_trace(go.Scatter(
                        x=sub_df['Date'],
                        y=sub_df['Weight'],
                        mode='lines+markers',
                        line_shape='hv',
                        name=code,
                        line=dict(width=3, color=color_seq[i % len(color_seq)])
                    ))
                fig.update_layout(
                    title=f"📊 {sel_name} 各 ETF 每日權重佔比",
                    height=450,
                    hovermode="x unified",
                    xaxis_title="日期",
                    yaxis_title="權重 (%)",
                    margin=dict(t=50, l=10, r=10, b=10)
                )
                # 強制使用類別型態，消去假日空白斷層
                fig.update_xaxes(type='category', categoryorder='category ascending', nticks=15)
                st.plotly_chart(fig, use_container_width=True)
                st.warning("此區間內無 OHLC 資料，僅顯示權重折線圖。")
                
            pivot_df = df_stock.pivot(index='Date', columns='ETF_Code', values='Weight').fillna(0).sort_index(ascending=False)
            st.dataframe(pivot_df.style.format("{:.2f}%"), use_container_width=True)
        else:
            st.info("此區間內無該股票的歷史異動數據。")

    # ==========================================
    # 7. 成分股權重與區間漲跌幅熱力圖 (置於最底)
    # ==========================================
    st.markdown("---")
    st.markdown("<h3 style='font-size: 28px;'>🗺️ 成分股權重與區間漲跌幅熱力圖</h3>", unsafe_allow_html=True)
    
    @st.cache_data(ttl=600)
    def calc_price_change(stock_symbol, d_prev, d_latest):
        import os
        import pandas as pd
        csv_path = os.path.join("price_downloader", "hist_prices", f"{stock_symbol}.csv")
        if not os.path.exists(csv_path): return 0.0
        try:
            df_price = pd.read_csv(csv_path)
            df_price['Date'] = pd.to_datetime(df_price['Date'])
            df_price = df_price.sort_values(by='Date')
            d1 = pd.to_datetime(d_prev)
            d2 = pd.to_datetime(d_latest)
            df_range = df_price[(df_price['Date'] >= d1) & (df_price['Date'] <= d2)]
            if len(df_range) < 1: return 0.0
            
            start_price = df_range.iloc[0]['Close']
            end_price = df_range.iloc[-1]['Close']
            if start_price > 0:
                return (end_price - start_price) / start_price * 100
        except:
            pass
        return 0.0

    # 針對篩選後的合併資料計算每一檔股價的漲跌幅
    if '漲跌幅(%)' not in merged.columns:
        merged['漲跌幅(%)'] = merged['Stock_Symbol'].apply(lambda x: calc_price_change(x, date_prev, date_latest))
    
    tm_df = merged[merged['Weight_Latest'] > 0].copy()
    if not tm_df.empty:
        tm_df['Text_Format'] = tm_df['漲跌幅(%)'].apply(lambda x: f"{x:+.2f}%")
        
        # 根據你提供的附圖自訂色階，並固定範圍落在 -10% 到 10%
        custom_color_scale = [
            (0.00, "#09622a"), # -10% (深綠)
            (0.05, "#157f35"), # -9%
            (0.20, "#2fa854"), # -6%
            (0.35, "#42c067"), # -3%
            (0.50, "#c2c6cc"), # 0% (淺灰)
            (0.65, "#ff7d86"), # +3%
            (0.80, "#f63344"), # +6%
            (0.95, "#a9262d"), # +9%
            (1.00, "#8e181e")  # +10% (深紅)
        ]

        fig = px.treemap(
            tm_df,
            path=['Stock_Name'], 
            values='Weight_Latest',
            color='漲跌幅(%)',
            custom_data=['Text_Format'],
            range_color=[-10, 10], # 鎖定比例尺，讓漸層分佈不會因為極端值跑掉
            color_continuous_scale=custom_color_scale,
            color_continuous_midpoint=0
        )
        fig.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=650) # 高度調大一點更好看
        fig.update_traces(
            texttemplate="%{label}<br>%{customdata[0]}", 
            textfont=dict(color='white'), 
            textposition='middle center', # 強制垂直置中
            hovertemplate='<b>%{label}</b><br>權重占比: %{value:.2f}%<br>區間漲跌幅: %{color:.2f}%',
            marker=dict(line=dict(color='#000000', width=1.5)) # 讓每個方塊之間使用黑色分隔線
        )
        
        # 關閉 Streamlit 預設主題 (theme=None)
        st.plotly_chart(fig, use_container_width=True, theme=None)
    else:
        st.info("目前選擇的日期或標的無有效的權重資料繪製熱力圖。")