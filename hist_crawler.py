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

def clean_and_format_data(df, etf_code, target_date=None):
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
    # 如果有輸入歷史日期，就用歷史日期，否則用今天
    df['Date'] = target_date if target_date else datetime.today().strftime('%Y-%m-%d')
    return df[['Date', 'ETF_Code', 'Stock_Symbol', 'Stock_Name', 'Weight']]

def fetch_etf_data(driver, etf_code, url, target_date=None):
    print(f"🔍 正在處理 {etf_code} (日期: {target_date if target_date else '今日'})...")
    driver.get(url)
    time.sleep(4) 
    
    try:
        # ==========================================
        # 🎯 00991A (復華) - 歷史日期版邏輯框架
        # ==========================================
        if etf_code == "00991A":
            # 1. 切換頁籤
            driver.execute_script("let tabs = Array.from(document.querySelectorAll('a, li, div')); let target = tabs.find(t => t.textContent.includes('基金資產') && t.offsetParent !== null); if(target) target.click();")
            print("   👉 已切換至復華「基金資產」頁籤")
            time.sleep(3)
            
            # 🌟 [戰略突破口 1]：在這裡修改日期！
            if target_date:
                # 復華的 flatpickr 格式是 YYYY/MM/DD
                formatted_date = target_date.replace("-", "/")
                print(f"   ⏳ 準備切換歷史日期至 {formatted_date}...")
                
                # 繞過 flatpickr readonly，設定 value
                driver.execute_script(f"""
                    let el = document.querySelector('input.flatpickr-input');
                    if (el) {{
                        el.value = '{formatted_date}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        
                        // 針對可能有 flatpickr 實例掛在 DOM 上的情況，也觸發 setDate
                        if(el._flatpickr) {{
                            el._flatpickr.setDate('{formatted_date}');
                        }}
                    }}
                """)
                time.sleep(1)
                
                # 找出「查詢」按鈕並點擊
                print("   👉 正在點擊「查詢」按鈕...")
                driver.execute_script("""
                    let buttons = Array.from(document.querySelectorAll('button, a, div'));
                    // 尋找包含「查詢」字眼的按鈕或可點擊元素
                    let searchBtn = buttons.find(b => b.textContent && b.textContent.trim() === '查詢' && b.offsetParent !== null);
                    if(searchBtn) {{
                        searchBtn.click();
                    }} else {{
                        // fallback: 如果找不到精確字眼，就找任何裡面的查詢
                        let fallbackBtn = buttons.find(b => b.textContent && b.textContent.includes('查詢') && b.offsetParent !== null && b.tagName === 'BUTTON');
                        if (fallbackBtn) fallbackBtn.click();
                    }}
                """)
                time.sleep(5) # 等待資料載入
            
            # 2. 定位按鈕展開更多
            print("   🚀 正在點擊「展開更多」按鈕...")
            driver.execute_script("""
                let btn = document.querySelector('button.fundTable-toggle');
                if(btn) { btn.click(); }
            """)
            time.sleep(5)
            
            table_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'etfStockTable')]"))
            )
            html_content = table_element.get_attribute('outerHTML')
            
            df = pd.read_html(io.StringIO(html_content), flavor='html5lib')[0]
            col_str = "".join(df.columns.astype(str))
            if '代' not in col_str and '名' not in col_str:
                df.columns = df.iloc[0]
                df = df[1:].reset_index(drop=True)
                
            clean_df = clean_and_format_data(df, etf_code, target_date)
            if not clean_df.empty:
                print(f"   ✅ {etf_code} 成功抓取！總共：{len(clean_df)} 筆持股")
                return clean_df

        # ==========================================
        # 🎯 00980A (野村) - 歷史日期版邏輯框架
        # ==========================================
        elif etf_code == "00980A":
            time.sleep(3)
            
            # 🌟 [戰略突破口 2]：在這裡修改日期！
            if target_date:
                # 截圖顯示野村格式是 YYYY/MM/DD
                formatted_date = target_date.replace("-", "/")
                print(f"   ⏳ 準備切換歷史日期至 {formatted_date}...")

                # 透過 JavaScript 繞過 readonly，直接給值並觸發 Angular (matinput) 內部事件更新查詢
                driver.execute_script(f"""
                    let el = document.querySelector('input.mat-datepicker-input');
                    if (el) {{
                        el.value = '{formatted_date}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    }}
                """)
                # 點擊完日期後需要等待 Angular 重新連 Server 拿資料，重新渲染表格
                time.sleep(5)

            # 檢查是否有無資料的提示文字
            if "此搜尋條件尚無相關資料" in driver.page_source:
                print(f"   ⚠️ {etf_code} 抓取失敗：該日期 ({target_date}) 尚無相關資料")
                return pd.DataFrame()

            print("   👉 正在點擊野村「查看更多」按鈕...")
            driver.execute_script("""
                let btn = document.querySelector('td.showMore p') || document.querySelector('td.showMore');
                if(btn) { btn.click(); }
            """)
            time.sleep(5) 
            
            html_content = driver.page_source
            try:
                dfs = pd.read_html(io.StringIO(html_content), flavor='html5lib')
            except ValueError:
                # 捕獲 No tables found，避免整個跳出
                dfs = []
                
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
                    clean_df = clean_and_format_data(df, etf_code, target_date)
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
    print("🚀 歷史 ETF 持股抓取腳本...")
    driver = setup_driver()
    
    etf_list = [
        {"code": "00991A", "url": "https://www.fhtrust.com.tw/ETF/etf_detail/ETF23#stockhold"},
        {"code": "00980A", "url": "https://www.nomurafunds.com.tw/ETFWEB/product-description?fundNo=00980A&tab=Shareholding"}
    ]
    
    # 這裡可以修改為您想抓取的歷史日期
    target_date = "2024-03-16"
    
    all_results = []
    for item in etf_list:
        df = fetch_etf_data(driver, item["code"], item["url"], target_date)
        if not df.empty:
            all_results.append(df)
            
    driver.quit()
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df = final_df.drop_duplicates(subset=['Date', 'ETF_Code', 'Stock_Symbol'])
        save_to_sqlite(final_df)
        print(f"\n🎉 {target_date} ETF 持股明細已完整抓取完畢！")
    else:
        print("\n⚠️ 此次執行未獲取任何有效資料。")

if __name__ == "__main__":
    main()