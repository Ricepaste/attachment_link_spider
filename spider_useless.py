from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import time

# ---------------------
# ✅ 參數設定
# ---------------------
root_url = "https://oa-22.adm.ncu.edu.tw/"
target_file_url = "https://oa-22.adm.ncu.edu.tw/word/%E5%9C%8B%E7%AB%8B%E5%A4%A7%E5%AD%B8%E6%A0%A1%E9%99%A2%E6%A0%A1%E5%8B%99%E5%9F%BA%E9%87%91%E8%A8%AD%E7%BD%AE%E6%A2%9D%E4%BE%8B.pdf"
max_depth = 10
chromedriver_path = "chromedriver.exe"  # 修改成你的 chromedriver 路徑
max_workers = 10  # 同時最多多少個執行緒

# ---------------------
# ✅ 每層遞迴爬頁面連結
# ---------------------
def collect_all_links(driver, base_url, max_depth=2, current_depth=0, visited=None):
    if visited is None:
        visited = set()
    if current_depth > max_depth or base_url in visited:
        return visited

    visited.add(base_url)

    try:
        driver.get(base_url)
        time.sleep(1)
    except Exception as e:
        print(f"❌ Failed to open {base_url}, error: {e}")
        return visited

    # 一次性直接抓 hrefs，馬上存起來
    hrefs = []
    try:
        elements = driver.find_elements(By.TAG_NAME, "a")
        for elem in elements:
            href = elem.get_attribute("href")
            if href:
                hrefs.append(href)
    except Exception as e:
        print(f"⚠️ Error when extracting hrefs from {base_url}: {e}")
        return visited

    # 遞迴處理新找到的 href
    for href in hrefs:
        if href.startswith(root_url) and href not in visited:
            visited = collect_all_links(driver, href, max_depth, current_depth + 1, visited)

    return visited


# ---------------------
# ✅ 多執行緒檢查每個頁面是否包含目標連結
# ---------------------
def check_pages(urls, target_file_url):
    # 每個 thread 自己獨立 driver
    options = Options()
    # options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)

    found_pages = []

    for page_url in urls:
        try:
            driver.get(page_url)
            time.sleep(1)  # 等 JS 渲染

            html = driver.page_source
            if target_file_url in html:
                print(f"✅ Found target on: {page_url}")
                found_pages.append(page_url)
        except Exception as e:
            print(f"❌ Error on {page_url}: {e}")
            continue

    driver.quit()
    return found_pages

# ---------------------
# ✅ 分批執行多執行緒
# ---------------------
def run_multithread_check(all_page_urls, target_file_url, max_workers=3):
    results = []

    # 每個 batch 分 10 個 URL
    batches = [all_page_urls[i:i + 10] for i in range(0, len(all_page_urls), 10)]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_pages, batch, target_file_url) for batch in batches]
        for f in futures:
            results.extend(f.result())

    return results

# ---------------------
# ✅ 主流程
# ---------------------
if __name__ == "__main__":
    # 初始化 driver 先抓連結
    options = Options()
    # options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)

    print("🔎 Collecting all internal page URLs...")
    all_page_urls = collect_all_links(driver, root_url, max_depth=max_depth)
    driver.quit()
    all_page_urls = list(all_page_urls)
    print(f"✅ Collected {len(all_page_urls)} pages.")

    # 多執行緒檢查
    found_pages = run_multithread_check(all_page_urls, target_file_url, max_workers=max_workers)

    print("\n--- ✅ Pages containing the target file link ---")
    for page in found_pages:
        print(page)
