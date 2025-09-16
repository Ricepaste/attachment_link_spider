import json
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import os

# --- 配置區 ---
START_URL = 'https://scholars.ncu.edu.tw/zh/publications/?organisationIds=3e96fdff-eb87-4166-8e98-56399da65648&nofollow=true&publicationYear=2022&publicationYear=2023&publicationYear=2024' # 更新後的 URL
OUTPUT_FILENAME = 'ncu_papers_selenium_updated.json'
WAIT_TIMEOUT = 45 # 等待元素出現的超時時間（秒）
PAGE_LOAD_TIMEOUT = 120 # 頁面載入總超時時間
STABILITY_PAUSE_TIME = 3 # 載入或滾動後額外等待時間
SCREENSHOT_DIR = 'screenshots' # 截圖保存目錄

HEADLESS_MODE = False # 建議一開始設為 False，觀察瀏覽器行為
USER_DATA_DIR = os.path.join(os.getcwd(), 'selenium_user_data')

# --- 函數區 (與之前相同，略) ---
def initialize_driver(headless=True, user_data_dir=None):
    """初始化 undetected_chromedriver"""
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    
    if user_data_dir:
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
        options.add_argument(f"--user-data-dir={user_data_dir}")
        print(f"使用用戶資料目錄: {user_data_dir}")

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver

def take_screenshot(driver, name):
    """拍攝螢幕截圖並保存"""
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    filepath = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    try:
        driver.save_screenshot(filepath)
        print(f"截圖已保存: {filepath}")
    except Exception as e:
        print(f"保存截圖失敗: {e}")

def scroll_page(driver):
    """模擬人類滾動行為"""
    print("模擬人類滾動行為...")
    driver.execute_script("window.scrollTo(0, Math.random() * window.innerHeight);")
    time.sleep(STABILITY_PAUSE_TIME)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
    time.sleep(STABILITY_PAUSE_TIME)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(STABILITY_PAUSE_TIME)
    print("滾動模擬完成。")

def scrape_page_data(driver, page_num):
    """抓取當前頁面的論文數據"""
    data = []
    
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'li.list-result-item'))
        )
        time.sleep(STABILITY_PAUSE_TIME)
        
        if "Just a moment..." in driver.page_source or "Enable JavaScript and cookies to continue" in driver.page_source:
            print(f"錯誤: 頁面 {page_num+1} 在等待後仍然是 Cloudflare 挑戰頁面。")
            take_screenshot(driver, f"page_{page_num}_cloudflare_after_wait")
            return []

        paper_blocks = driver.find_elements(By.CSS_SELECTOR, 'li.list-result-item')
        print(f"找到 {len(paper_blocks)} 篇論文在當前頁面。")
        take_screenshot(driver, f"page_{page_num}_after_load")

        if not paper_blocks:
            print(f"警告: 雖然等待成功，但當前頁面 {page_num+1} 沒有找到論文區塊。")
            return data

        for i, block in enumerate(paper_blocks):
            title = None
            linked_authors = []

            try:
                title_elem = block.find_element(By.CSS_SELECTOR, 'div.result-container h3 a')
                title = title_elem.text.strip()
            except NoSuchElementException:
                pass

            try:
                # *** 主要修改這裡：從<a>標籤內部尋找<span>標籤來獲取文本 ***
                # 選擇器保持不變，選中<a>標籤
                author_link_elements = block.find_elements(By.CSS_SELECTOR, 'div.result-container div.rendering a[rel="Person"][href*="/persons/"]')
                for author_link_elem in author_link_elements:
                    # 在每個找到的 <a> 標籤內，尋找 <span> 標籤並獲取其文本
                    try:
                        author_span_elem = author_link_elem.find_element(By.TAG_NAME, 'span')
                        author_name = author_span_elem.text.strip()
                        if author_name:
                            linked_authors.append(author_name)
                    except NoSuchElementException:
                        # 如果 <a> 內沒有 <span>，則嘗試直接獲取 <a> 的文本
                        author_name = author_link_elem.text.strip()
                        if author_name:
                            linked_authors.append(author_name)
            except NoSuchElementException:
                pass
            except StaleElementReferenceException:
                print(f"警告: 頁面 {page_num+1}, 第 {i+1} 篇論文在處理作者時遇到 StaleElementReferenceException。")
                pass 

            data.append({
                'title': title,
                'linked_authors': linked_authors
            })
    except TimeoutException:
        print(f"警告: 頁面 {page_num+1} 等待論文列表超時，當前頁面可能沒有論文或載入失敗。")
        take_screenshot(driver, f"page_{page_num}_timeout")
    except Exception as e:
        print(f"抓取頁面 {page_num+1} 數據時發生錯誤: {e}")
        take_screenshot(driver, f"page_{page_num}_error")
        
    return data

# --- 主函數 (與之前相同，略) ---
def main():
    all_papers = []
    page_num = 0
    driver = None

    try:
        driver = initialize_driver(headless=HEADLESS_MODE, user_data_dir=USER_DATA_DIR)

        print(f"導航到起始 URL: {START_URL}")
        driver.get(START_URL)

        print("等待 Cloudflare 挑戰或頁面主要內容載入...")
        try:
            WebDriverWait(driver, 60).until_not(EC.title_contains("Just a moment..."))
            WebDriverWait(driver, 60).until_not(EC.presence_of_element_located((By.ID, "cf-wrapper")))
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'li.list-result-item'))
            )
            print("論文列表已載入。Cloudflare 挑戰可能已成功繞過。")
            take_screenshot(driver, "initial_load_success")
            scroll_page(driver)
            time.sleep(STABILITY_PAUSE_TIME * 2)

        except TimeoutException:
            print("錯誤: Cloudflare 挑戰或主要內容載入超時。請檢查瀏覽器窗口或截圖。")
            take_screenshot(driver, "cloudflare_challenge_failed_timeout")
            return
        except Exception as e:
            print(f"首次載入時發生錯誤: {e}")
            take_screenshot(driver, "initial_load_error")
            return

        while True:
            print(f"\n--- 正在抓取第 {page_num + 1} 頁 ---")
            current_page_papers = scrape_page_data(driver, page_num)
            all_papers.extend(current_page_papers)

            if not current_page_papers and page_num > 0:
                print("當前頁面沒有抓取到論文，可能已達最後一頁或載入失敗。停止爬取。")
                break 
            
            if not current_page_papers and page_num == 0 and not all_papers:
                 print("第一頁就沒有抓取到論文，停止爬取。")
                 break

            page_num += 1
            next_page_url = f"{START_URL.split('&page=')[0]}&page={page_num}"

            print(f"嘗試導航到下一頁: {next_page_url}")
            try:
                driver.get(next_page_url)
                WebDriverWait(driver, 60).until_not(EC.title_contains("Just a moment..."))
                WebDriverWait(driver, 60).until_not(EC.presence_of_element_located((By.ID, "cf-wrapper")))
                WebDriverWait(driver, WAIT_TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'li.list-result-item'))
                )
                time.sleep(STABILITY_PAUSE_TIME)
                scroll_page(driver)

            except TimeoutException:
                print(f"導航到第 {page_num + 1} 頁或等待論文列表超時。可能已無下一頁或載入失敗。")
                take_screenshot(driver, f"page_{page_num}_navigation_timeout")
                break
            except Exception as e:
                print(f"導航到第 {page_num + 1} 頁時發生錯誤: {e}")
                take_screenshot(driver, f"page_{page_num}_navigation_error")
                break


    except TimeoutException as e:
        print(f"主要爬取流程超時錯誤: {e}")
    except Exception as e:
        print(f"爬取過程中發生未知錯誤: {e}")
    finally:
        if driver:
            print("關閉瀏覽器。")
            driver.quit()

        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(all_papers, f, ensure_ascii=False, indent=4)
        print(f"\n爬取完成。共抓取到 {len(all_papers)} 篇論文。數據已保存到 {OUTPUT_FILENAME}")

if __name__ == '__main__':
    main()