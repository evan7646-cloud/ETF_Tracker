import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,10000")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

url = "https://www.cathaysite.com.tw/ETF/detail/EEA?tab=etf3"
driver.get(url)
print("Page loaded")
time.sleep(8)

driver.execute_script("""
    let btn = document.querySelector('.button-box');
    if(btn) { btn.click(); }
""")
time.sleep(3)

html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

box = soup.find('div', class_='bar_table_are')
if box:
    print("Found bar_table_are")
    bdy = box.find('div', class_='bar_table_body')
    if bdy:
        print("Found bar_table_body")
        for i, row in enumerate(bdy.find_all('div', recursive=False)[:2]):
            print(f"Row {i} html:", row)
else:
    print("Could not find table")

driver.quit()
