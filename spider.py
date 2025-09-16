from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote, urlparse
import time

def normalize_url(base_url, href):
    """補完整 URL，處理中文/特殊字元編碼"""
    joined_url = urljoin(base_url, href)
    joined_url = unquote(joined_url)
    final_url = quote(joined_url, safe="/:?&=%#")
    return final_url

def find_pages_linking_to_file_selenium(root_url, target_file_url, max_depth=3):
    visited = set()
    to_visit = [(root_url, 0)]
    found_on_pages = []
    failed_links = []

    # 初始化 Selenium
    options = Options()
    options.add_argument("--headless")
    # options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(service=Service("chromedriver.exe"), options=options)

    # 統一去除最後 /
    target_file_url = target_file_url.rstrip("/")

    while to_visit:
        current_url, depth = to_visit.pop()
        if current_url in visited or depth > max_depth:
            continue

        print(f"🔎 Crawling: {current_url} (depth: {depth})")
        try:
            driver.get(current_url)
            time.sleep(1)  # 給 JS 一點渲染時間
            html = driver.page_source
        except WebDriverException as e:
            print(f"⚠️ Failed to fetch {current_url}: {e}")
            failed_links.append(current_url)
            continue

        visited.add(current_url)
        soup = BeautifulSoup(html, "html.parser")

        has_link_to_target = False

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = normalize_url(current_url, href).rstrip("/")

            # 是否指向目標檔案
            if full_url == target_file_url:
                has_link_to_target = True

            # 加入新的頁面（同主網域才會再深入）
            if urlparse(full_url).netloc == urlparse(root_url).netloc and full_url not in visited:
                to_visit.append((full_url, depth + 1))

        if has_link_to_target:
            print(f"✅ Page linking to target: {current_url}")
            found_on_pages.append(current_url)

    driver.quit()

    # 結果
    print("\n✅✅ Finished!")
    print("--- Pages that link to the target file ---")
    if found_on_pages:
        for page in found_on_pages:
            print(page)
    else:
        print("⚠️ No pages found linking to the target file.")

    if failed_links:
        print("\n❌ Failed pages:")
        for fail in failed_links:
            print(fail)

    return found_on_pages, failed_links

# =========== 使用範例 ===========
root_site = "https://ncu.edu.tw/rd/"
target_file = "https://in.ncu.edu.tw/ncu7020/Files/Research/8.(%E7%A0%94%E7%99%BC%E6%9C%83%E5%BE%8C%E4%BF%AE%E6%AD%A3)-%E6%95%99%E5%B8%AB%E7%B8%BE%E5%84%AA%E5%B0%88%E5%88%A9%E5%8F%8A%E6%8A%80%E8%BD%89%E7%8D%8E%E5%8B%B5%E8%BE%A6%E6%B3%95.pdf"

find_pages_linking_to_file_selenium(root_site, target_file, max_depth=10)
