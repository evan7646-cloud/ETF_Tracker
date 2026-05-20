import sqlite3
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import base64
import os

# ==========================================
# 1. 網頁基本設定與自訂標題
# ==========================================
st.set_page_config(page_title="主動式ETF追蹤儀表板", layout="wide", page_icon="📈", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    div[role="radiogroup"] > label {
        padding: 10px 15px;
        margin-bottom: 5px;
        border-radius: 8px;
        transition: background-color 0.2s;
    }
    div[role="radiogroup"] > label:hover {
        background-color: #e9ecef;
    }
    div[role="radiogroup"] > label[data-checked="true"] {
        background-color: #fdf5e6;
        font-weight: bold;
        color: #d97706;
    }
    div[role="radiogroup"] div[data-testid="stMarkdownContainer"] p {
        font-size: 16px;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

logo_base64 = ""
if os.path.exists("logo.png"):
    with open("logo.png", "rb") as image_file:
        logo_base64 = base64.b64encode(image_file.read()).decode()

@st.cache_data(ttl=60)
def load_data():
    conn = sqlite3.connect('etf_holdings.db')
    df = pd.read_sql("SELECT * FROM daily_weights", conn)
    conn.close()
    return df

def get_last_price_update():
    ts_path = os.path.join("price_downloader", "last_price_update.txt")
    if os.path.exists(ts_path):
        with open(ts_path, 'r') as f:
            return f.read().strip()
    return None

df_raw = load_data()

# ==========================================
# 側邊欄設計 (日期在上、選單在下)
# ==========================================
with st.sidebar:
    # 標題與 Logo (還原原本的設計)
    col1, col2 = st.columns([1, 5])
    with col1:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=36)
    with col2:
        st.markdown("<span style='color: #CD002A; font-weight: 900; font-size: 24px; display:flex; align-items:center; height:100%;'>國票期貨法人部製作</span>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; font-size: 18px; margin-top: -5px;'>主動式ETF：籌碼流向儀表板</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # 1. 日期選擇 (移到選單上方)
    st.markdown("### 📅 日期與區間設定")
    if not df_raw.empty:
        df_raw['Date'] = pd.to_datetime(df_raw['Date'], format='mixed').dt.strftime('%Y-%m-%d')
        all_dates = sorted(df_raw['Date'].unique(), reverse=True)
        
        if len(all_dates) >= 2:
            min_date = pd.to_datetime(all_dates[-1]).date()
            max_date = pd.to_datetime(all_dates[0]).date()
            
            default_latest = max_date
            default_prev = pd.to_datetime(all_dates[1]).date()
            
            date_prev_obj = st.date_input("🗓️ 過去日期 (T-N)", value=default_prev, min_value=min_date, max_value=max_date)
            date_latest_obj = st.date_input("🗓️ 最新日期 (T)", value=default_latest, min_value=min_date, max_value=max_date)
            
            date_latest = date_latest_obj.strftime('%Y-%m-%d')
            date_prev = date_prev_obj.strftime('%Y-%m-%d')
        else:
            st.info("等待資料累積中...")
            st.stop()
    else:
        st.warning("⚠️ 資料庫目前沒有資料！")
        st.stop()

    st.markdown("---")


    # 2. ETF 篩選
    with st.expander("🎯 篩選觀測標的", expanded=False):
        available_etf_codes = sorted(df_raw['ETF_Code'].unique())
        selected_etfs = []
        if "select_all" not in st.session_state:
            st.session_state.select_all = True

        def toggle_all():
            for code in available_etf_codes:
                st.session_state[f"cb_{code}"] = st.session_state.select_all

        st.checkbox("✅ 全選所有 ETF", key="select_all", on_change=toggle_all)
        
        for code in available_etf_codes:
            if f"cb_{code}" not in st.session_state:
                st.session_state[f"cb_{code}"] = st.session_state.select_all
            if st.checkbox(code, key=f"cb_{code}"):
                selected_etfs.append(code)
    
    # 3. 選單 (使用原本的項目作為分頁)
    st.markdown("### 📍 功能分頁")
    menu_options = [
        "🏆 持股變動綜合排行",
        "📝 成分股調倉明細單",
        "📈 歷史 K 線與權重對照圖",
        "🔲 成分股持股熱力圖"
    ]
    selected_page = st.radio("導覽清單", menu_options, label_visibility="collapsed")
    
    st.markdown("---")
    


# 防呆檢查
if not selected_etfs:
    st.error("❌ 請至少勾選一檔 ETF！")
    st.stop()

# ==========================================
# 資料運算 (所有分頁共用的基礎資料)
# ==========================================
df_filtered = df_raw[df_raw['ETF_Code'].isin(selected_etfs)]
df_latest = df_filtered[df_filtered['Date'] == date_latest]
df_prev = df_filtered[df_filtered['Date'] == date_prev]

tot_latest = df_latest.groupby('Stock_Symbol').agg({'Stock_Name': 'first', 'Weight': 'sum'}).reset_index()
tot_prev = df_prev.groupby('Stock_Symbol').agg({'Stock_Name': 'first', 'Weight': 'sum'}).reset_index()

merged = pd.merge(tot_latest, tot_prev, on='Stock_Symbol', suffixes=('_Latest', '_Prev'), how='outer')
merged['Stock_Name'] = merged['Stock_Name_Latest'].fillna(merged['Stock_Name_Prev'])
merged = merged.fillna(0)
merged['Delta(%)'] = merged['Weight_Latest'] - merged['Weight_Prev']

etf_detail_latest = df_latest[['Stock_Symbol', 'ETF_Code', 'Weight']]
etf_detail_prev = df_prev[['Stock_Symbol', 'ETF_Code', 'Weight']]

etf_merged = pd.merge(etf_detail_latest, etf_detail_prev, on=['Stock_Symbol', 'ETF_Code'], suffixes=('_L', '_P'), how='outer').fillna(0)
etf_merged['ETF_Delta'] = etf_merged['Weight_L'] - etf_merged['Weight_P']
etf_merged = etf_merged[etf_merged['ETF_Delta'].abs() > 0.001].copy() 

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

# ==========================================
# 主畫面內容
# ==========================================

if selected_page == "🏆 持股變動綜合排行":
    st.markdown("<h2 style='font-size: 26px; margin-bottom: 0;'>🔥 投信集體【加碼】排行榜</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; margin-top: 5px; margin-bottom: 5px;'>投信資金集中押注或大幅撤出的熱門標的。</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #64748b; margin-top: 0; margin-bottom: 20px;'>目前比較區間：<b>{date_prev}</b> ➔ <b>{date_latest}</b></p>", unsafe_allow_html=True)
    
    top_buy = merged[merged['Delta(%)'] > 0].sort_values(by='Delta(%)', ascending=False).head(15)
    top_buy['Label'] = top_buy['Stock_Name'] + ';;(' + top_buy['Stock_Symbol'] + ')'
    if not top_buy.empty:
        chart_buy = alt.Chart(top_buy).mark_bar(color="#ff4b4b").encode(
            x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')", labelFontSize=16, titleFontSize=14)),
            y=alt.Y('Delta(%)', title="加碼幅度 (%)"),
            tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('Delta(%)', format='.2f')]
        ).properties(height=400)
        st.altair_chart(chart_buy, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-size: 26px;'>🧊 投信集體【調節】排行榜</h3>", unsafe_allow_html=True)
    top_sell = merged[merged['Delta(%)'] < 0].sort_values(by='Delta(%)', ascending=True).head(15)
    top_sell['Label'] = top_sell['Stock_Name'] + ';;(' + top_sell['Stock_Symbol'] + ')'
    if not top_sell.empty:
        top_sell['調節幅度(%)'] = top_sell['Delta(%)'].abs()
        chart_sell = alt.Chart(top_sell).mark_bar(color="#00cc96").encode(
            x=alt.X('Label', sort=None, axis=alt.Axis(labelAngle=0, title="股票名稱", labelExpr="split(datum.value, ';;')", labelFontSize=16, titleFontSize=14)),
            y=alt.Y('調節幅度(%)', title="調節幅度 (%)"),
            tooltip=['Stock_Symbol', 'Stock_Name', alt.Tooltip('調節幅度(%)', format='.2f')]
        ).properties(height=400)
        st.altair_chart(chart_sell, use_container_width=True)

elif selected_page == "📝 成分股調倉明細單":
    st.markdown("<h2 style='font-size: 32px; margin-bottom: 0;'>📋 完整成分股變動明細</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; margin-top: 5px; margin-bottom: 5px;'>列出各支 ETF 對特定股票的加減碼操作 (包含前次與最新權重狀態)。</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #64748b; margin-top: 0; margin-bottom: 20px;'>目前比較區間：<b>{date_prev}</b> ➔ <b>{date_latest}</b></p>", unsafe_allow_html=True)
    
    def check_status(row):
        if row['Weight_Prev'] == 0 and row['Weight_Latest'] > 0: return '🌟 新納入'
        if row['Weight_Latest'] == 0 and row['Weight_Prev'] > 0: return '❌ 已剔除'
        return '-'
    merged['狀態'] = merged.apply(check_status, axis=1)
    display_df = merged[['狀態', 'Stock_Symbol', 'Stock_Name', 'Weight_Latest', 'Weight_Prev', 'Delta(%)', '▲ 加碼 ETF', '▼ 調節 ETF']].rename(columns={
        'Stock_Symbol': '股票代號', 'Stock_Name': '股票名稱', 'Weight_Latest': f'{date_latest} 總權重(%)', 'Weight_Prev': f'{date_prev} 總權重(%)', 'Delta(%)': '兩期總變動(%)'
    }).sort_values(by='兩期總變動(%)', key=abs, ascending=False)
    
    def highlight_rows(row):
        if row['狀態'] == '🌟 新納入': return ['background-color: rgba(231, 76, 60, 0.15)'] * len(row) 
        if row['狀態'] == '❌ 已剔除': return ['background-color: rgba(46, 204, 113, 0.15)'] * len(row)  
        return [''] * len(row)
    def color_text(val, color):
        return f'color: {color};' if val != '-' else ''

    styled_df = display_df.style.apply(highlight_rows, axis=1)\
        .map(lambda x: color_text(x, '#ff4b4b'), subset=['▲ 加碼 ETF'])\
        .map(lambda x: color_text(x, '#00cc96'), subset=['▼ 調節 ETF'])\
        .format({f'{date_latest} 總權重(%)': '{:.2f}%', f'{date_prev} 總權重(%)': '{:.2f}%', '兩期總變動(%)': '{:+.2f}%'})
    
    st.dataframe(
        styled_df, 
        use_container_width=True, 
        height=600, 
        hide_index=True,
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

elif selected_page == "📈 歷史 K 線與權重對照圖":
    st.markdown("<h2 style='font-size: 32px; margin-bottom: 0;'>🔍 股票搜尋與動態追蹤</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; margin-top: 5px; margin-bottom: 5px;'>將股價走勢結合階梯式的持股權重變動。</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #64748b; margin-top: 0; margin-bottom: 20px;'>目前比較區間：<b>{date_prev}</b> ➔ <b>{date_latest}</b></p>", unsafe_allow_html=True)
    
    all_stocks = sorted(merged[merged['Weight_Latest'] > 0]['Stock_Symbol'].unique())
    if all_stocks:
        selected_stock = st.selectbox("選擇股票代號進行查詢", all_stocks)
        sel_symbol = selected_stock
        sel_name = merged[merged['Stock_Symbol'] == sel_symbol]['Stock_Name'].iloc[0]
        
        price_ts = get_last_price_update()
        ts_badge = f"　<span style='font-size:14px; color:#888;'>📡 股價更新: {price_ts}</span>" if price_ts else ""
        st.markdown(f"### {sel_name} ({sel_symbol}) - 區間走勢與權重動態{ts_badge}", unsafe_allow_html=True)
        
        csv_path = os.path.join("price_downloader", "hist_prices", f"{sel_symbol}.csv")
        has_kline = False
        df_range = pd.DataFrame()
        if os.path.exists(csv_path):
            df_price = pd.read_csv(csv_path)
            df_price['Date'] = pd.to_datetime(df_price['Date'])
            d1 = pd.to_datetime(date_prev)
            df_range = df_price[df_price['Date'] >= d1].copy()
            if not df_range.empty: has_kline = True

        df_stock = df_filtered[(df_filtered['Stock_Symbol'] == sel_symbol) & (df_filtered['Date'] >= date_prev) & (df_filtered['Date'] <= date_latest)].copy()
        if not df_stock.empty:
            df_stock['Date'] = pd.to_datetime(df_stock['Date'])
            if has_kline:
                kline_dates = set(df_range['Date'].dt.strftime('%Y-%m-%d'))
                weight_dates = set(df_stock['Date'].dt.strftime('%Y-%m-%d'))
                all_dates_union = sorted(kline_dates | weight_dates)
                df_range['Date_str'] = df_range['Date'].dt.strftime('%Y-%m-%d')
                df_stock['Date_str'] = df_stock['Date'].dt.strftime('%Y-%m-%d')

                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.5, 0.5])
                fig.add_trace(go.Candlestick(x=df_range['Date_str'], open=df_range['Open'], high=df_range['High'], low=df_range['Low'], close=df_range['Close'], name="K線走勢", increasing_line_color='#ef313d', increasing_fillcolor='#ef313d', decreasing_line_color='#36a555', decreasing_fillcolor='#36a555'), row=1, col=1)
                
                etf_codes = df_stock['ETF_Code'].unique()
                color_seq = px.colors.qualitative.Plotly
                for i, code in enumerate(etf_codes):
                    sub_df = df_stock[df_stock['ETF_Code'] == code].sort_values('Date')
                    fig.add_trace(go.Scatter(x=sub_df['Date_str'], y=sub_df['Weight'], mode='lines+markers', line_shape='hv', name=code, line=dict(width=3, color=color_seq[i % len(color_seq)]), hovertemplate='ETF: ' + code + '<br>權重: %{y:.2f}%<extra></extra>'), row=2, col=1)
                
                fig.update_layout(xaxis_rangeslider_visible=False, height=750, margin=dict(t=30, l=10, r=10, b=10), hovermode="x unified")
                fig.update_yaxes(title_text="股價 (TWD)", row=1, col=1)
                fig.update_yaxes(title_text="權重 (%)", row=2, col=1)
                fig.update_xaxes(type='category', categoryorder='array', categoryarray=all_dates_union, nticks=15)
                st.plotly_chart(fig, use_container_width=True)
            else:
                fig = go.Figure()
                etf_codes = df_stock['ETF_Code'].unique()
                color_seq = px.colors.qualitative.Plotly
                for i, code in enumerate(etf_codes):
                    sub_df = df_stock[df_stock['ETF_Code'] == code].sort_values('Date')
                    fig.add_trace(go.Scatter(x=sub_df['Date'], y=sub_df['Weight'], mode='lines+markers', line_shape='hv', name=code, line=dict(width=3, color=color_seq[i % len(color_seq)])))
                fig.update_layout(height=450, hovermode="x unified", xaxis_title="日期", yaxis_title="權重 (%)", margin=dict(t=50, l=10, r=10, b=10))
                fig.update_xaxes(type='category', categoryorder='category ascending', nticks=15)
                st.plotly_chart(fig, use_container_width=True)
                st.warning("此區間內無 OHLC 資料，僅顯示權重折線圖。")
            pivot_df = df_stock.pivot(index='Date', columns='ETF_Code', values='Weight').fillna(0).sort_index(ascending=False)
            st.dataframe(pivot_df.style.format("{:.2f}%"), use_container_width=True)
        else:
            st.info("此區間內無該股票的歷史異動數據。")

elif selected_page == "🔲 成分股持股熱力圖":
    price_ts_hm = get_last_price_update() 
    ts_hm_text = f"　<span style='font-size:14px; color:#888;'>📡 股價更新: {price_ts_hm}</span>" if price_ts_hm else ""
    st.markdown(f"<h2 style='font-size: 32px; margin-bottom: 0;'>🗺️ 成分股權重與區間漲跌幅熱力圖{ts_hm_text}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #64748b; margin-top: 5px; margin-bottom: 5px;'>顏色代表漲跌停，格子大小代表持股權重。</p>", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #64748b; margin-top: 0; margin-bottom: 20px;'>目前比較區間：<b>{date_prev}</b> ➔ <b>{date_latest}</b></p>", unsafe_allow_html=True)
    
    @st.cache_data(ttl=60)
    def calc_price_change(stock_symbol, d_prev):
        csv_path = os.path.join("price_downloader", "hist_prices", f"{stock_symbol}.csv")
        if not os.path.exists(csv_path): return 0.0
        try:
            df_price = pd.read_csv(csv_path)
            df_price['Date'] = pd.to_datetime(df_price['Date'])
            df_price = df_price.sort_values(by='Date')
            d1 = pd.to_datetime(d_prev)
            df_from = df_price[df_price['Date'] >= d1]
            if len(df_from) < 1: return 0.0
            start_price = df_from.iloc[0]['Close']
            end_price = df_price.iloc[-1]['Close']
            if start_price > 0: return (end_price - start_price) / start_price * 100
        except: pass
        return 0.0

    if '漲跌幅(%)' not in merged.columns:
        merged['漲跌幅(%)'] = merged['Stock_Symbol'].apply(lambda x: calc_price_change(x, date_prev))
    
    tm_df = merged[merged['Weight_Latest'] > 0].copy()
    if not tm_df.empty:
        tm_df['Text_Format'] = tm_df['漲跌幅(%)'].apply(lambda x: f"{x:+.2f}%")
        custom_color_scale = [
            (0.00, "#09622a"), (0.05, "#157f35"), (0.20, "#2fa854"), (0.35, "#42c067"),
            (0.50, "#c2c6cc"), (0.65, "#ff7d86"), (0.80, "#f63344"), (0.95, "#a9262d"), (1.00, "#8e181e")
        ]
        fig = px.treemap(tm_df, path=['Stock_Name'], values='Weight_Latest', color='漲跌幅(%)', custom_data=['Text_Format'], range_color=[-10, 10], color_continuous_scale=custom_color_scale, color_continuous_midpoint=0)
        fig.update_layout(margin=dict(t=30, l=10, r=10, b=10), height=650)
        fig.update_traces(texttemplate="%{label}<br>%{customdata[0]}", textfont=dict(color='white'), textposition='middle center', hovertemplate='<b>%{label}</b><br>權重占比: %{value:.2f}%<br>區間漲跌幅: %{color:.2f}%', marker=dict(line=dict(color='#000000', width=1.5)))
        st.plotly_chart(fig, use_container_width=True, theme=None)
    else:
        st.info("目前選擇的日期或標的無有效的權重資料繪製熱力圖。")