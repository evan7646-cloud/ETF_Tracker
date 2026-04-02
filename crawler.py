import os
import io
import time
import sqlite3
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,3000")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def clean_and_format_data(df, etf_code):
    rename_map = {}
    for col in df.columns:
        col_str = str(col).replace('\n', '').strip()
        if '代' in col_str: rename_map[col] = 'Stock_Symbol'
        elif '名' in col_str: rename_map[col] = 'Stock_Name'
        elif '重' in col_str or '%' in col_str: rename_map[col] = 'Weight'

    df = df.rename(columns=rename_map)
    required_cols = ['Stock_Symbol', 'Stock_Name', 'Weight']
    
    if not all(col in df.columns for col in required_cols):
        return pd.DataFrame()

    df = df[required_cols].copy()
    df['Weight'] = df['Weight'].astype(str).str.replace('%', '').str.strip()
    df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
    
    df = df.dropna(subset=['Stock_Symbol', 'Weight'])
    df = df[df['Stock_Symbol'].astype(str).str.contains(r'\d', na=False)] 
    
    df['ETF_Code'] = etf_code
    df['Date'] = datetime.today().strftime('%Y-%m-%d')
    return df[['Date', 'ETF_Code', 'Stock_Symbol', 'Stock_Name', 'Weight']]

def fetch_etf_data(driver, etf_code, url):
    print(f"🔍 正在處理 {etf_code}...")
    driver.get(url)
    time.sleep(4) 
    
    try:
        # ==========================================
        # 🎯 00981A (統一) - 維持原狀
        # ==========================================
        if etf_code == "00981A":
            driver.execute_script("let tabs = Array.from(document.querySelectorAll('a, li, span')); let target = tabs.find(t => t.textContent.includes('基金投資組合')); if(target) target.click();")
            time.sleep(2)
            driver.execute_script("let btn = document.getElementById('ShowStopListButton'); if(btn) btn.click();")
            print("   👉 已解鎖統一「展開全部」按鈕")
            time.sleep(3)
            
            html_content = driver.page_source
            dfs = pd.read_html(io.StringIO(html_content), flavor='html5lib')
            best_df = pd.DataFrame()
            for df in dfs:
                try:
                    if df.empty: continue
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
                    col_str = "".join(df.columns.astype(str))
                    if '代' not in col_str and '名' not in col_str:
                        if len(df) > 0:
                            df.columns = df.iloc[0]
                            df = df[1:].reset_index(drop=True)
                    clean_df = clean_and_format_data(df, etf_code)
                    if not clean_df.empty and len(clean_df) > len(best_df):
                        best_df = clean_df
                except: continue
            if not best_df.empty:
                print(f"   ✅ {etf_code} 成功抓取！總共：{len(best_df)} 筆持股")
                return best_df

        # ==========================================
        # 🎯 00991A (復華) - 精準鎖定 button class
        # ==========================================
        elif etf_code == "00991A":
            # 1. 切換頁籤
            driver.execute_script("let tabs = Array.from(document.querySelectorAll('a, li, div')); let target = tabs.find(t => t.textContent.includes('基金資產') && t.offsetParent !== null); if(target) target.click();")
            print("   👉 已切換至復華「基金資產」頁籤")
            time.sleep(3)
            
            # 2. 核心修正：利用您截圖提供的 fundTable-toggle 直接點擊
            print("   🚀 正在點擊「展開更多」按鈕...")
            driver.execute_script("""
                let btn = document.querySelector('button.fundTable-toggle');
                if(btn) { btn.click(); }
            """)
            
            # 給予網頁 5 秒鐘時間載入剩下的明細
            time.sleep(5)
            
            # 3. 抓取已經完全展開的表格
            table_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'etfStockTable')]"))
            )
            html_content = table_element.get_attribute('outerHTML')
            
            df = pd.read_html(io.StringIO(html_content), flavor='html5lib')[0]
            
            col_str = "".join(df.columns.astype(str))
            if '代' not in col_str and '名' not in col_str:
                df.columns = df.iloc[0]
                df = df[1:].reset_index(drop=True)
                
            clean_df = clean_and_format_data(df, etf_code)
            if not clean_df.empty:
                print(f"   ✅ {etf_code} 成功抓取！總共：{len(clean_df)} 筆持股")
                return clean_df

        # ==========================================
        # 🎯 00980A (野村) - 拔除滾動，精準點擊 + 掃描最大表
        # ==========================================
        else:
            time.sleep(3)
            print("   👉 正在點擊野村「查看更多」按鈕...")
            
            # 利用您截圖中的 td class="showMore" 精準點擊，不加入任何滾動
            driver.execute_script("""
                let btn = document.querySelector('td.showMore p') || document.querySelector('td.showMore');
                if(btn) { btn.click(); }
            """)
            
            # 給予 5 秒鐘讓資料展開
            time.sleep(5) 
            
            # 恢復使用 Pandas 掃描全網頁所有表格，選出「筆數最多」的那張，徹底避開錯誤表格
            html_content = driver.page_source
            dfs = pd.read_html(io.StringIO(html_content), flavor='html5lib')
            best_df = pd.DataFrame()
            
            for df in dfs:
                try:
                    if df.empty: continue
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(-1)
                    col_str = "".join(df.columns.astype(str))
                    if '代' not in col_str and '名' not in col_str:
                        if len(df) > 0:
                            df.columns = df.iloc[0]
                            df = df[1:].reset_index(drop=True)
                    clean_df = clean_and_format_data(df, etf_code)
                    if not clean_df.empty and len(clean_df) > len(best_df):
                        best_df = clean_df
                except: continue
                
            if not best_df.empty:
                print(f"   ✅ {etf_code} 成功抓取！總共：{len(best_df)} 筆持股")
                return best_df
            else:
                print(f"   ❌ {etf_code} 抓取失敗：找不到符合條件的持股表格")
            
    except Exception as e:
        print(f"   ❌ {etf_code} 執行異常: {e}")
        
    return pd.DataFrame()

def save_to_sqlite(df):
    if df.empty: return
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'etf_holdings.db')
    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(name='daily_weights', con=conn, if_exists='append', index=False)
        print(f"\n💾 資料庫寫入成功！本日總計新增：{len(df)} 筆")
    except Exception as e:
        print(f"❌ 寫入資料庫失敗: {e}")
    finally:
        conn.close()

def main():
    print("🚀 ETF 全自動持股追蹤系統 (按鈕狙擊版)...")
    driver = setup_driver()
    
    etf_list = [
        {"code": "00981A", "url": "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW"},
        {"code": "00991A", "url": "https://www.fhtrust.com.tw/ETF/etf_detail/ETF23#stockhold"},
        {"code": "00980A", "url": "https://www.nomurafunds.com.tw/ETFWEB/product-description?fundNo=00980A&tab=Shareholding"}
    ]
    
    all_results = []
    for item in etf_list:
        df = fetch_etf_data(driver, item["code"], item["url"])
        if not df.empty:
            all_results.append(df)
            
    driver.quit()
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df = final_df.drop_duplicates(subset=['Date', 'ETF_Code', 'Stock_Symbol'])
        save_to_sqlite(final_df)
        print("\n🎉 所有 ETF 持股明細已完整抓取完畢！")
    else:
        print("\n⚠️ 此次執行未獲取任何有效資料。")

if __name__ == "__main__":
    main()