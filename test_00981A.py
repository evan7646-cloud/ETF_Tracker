import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,3000")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

url = "https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=49YTW"
driver.get(url)
time.sleep(5)

print("Let's look for tab texts:")
tabs = driver.execute_script("""
    return Array.from(document.querySelectorAll('a, li, span, div.tab, a.tab'))
          .map(t => t.textContent.trim())
          .filter(t => t.length > 0 && t.length < 20);
""")
print(list(set(tabs)))

driver.quit()
