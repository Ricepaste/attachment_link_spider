import json
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import os
import re # 用於正則表達式處理作者字符串

# --- 配置區 ---
START_URL = 'https://scholars.ncu.edu.tw/zh/publications/?organisationIds=3e96fdff-eb87-4166-8e98-56399da65648&nofollow=true&publicationYear=2022&publicationYear=2023&publicationYear=2024'
OUTPUT_FILENAME = 'ncu_papers_selenium_full_authors.json' # 更新文件名
WAIT_TIMEOUT = 45
PAGE_LOAD_TIMEOUT = 120
STABILITY_PAUSE_TIME = 3
SCREENSHOT_DIR = 'screenshots'

HEADLESS_MODE = False
USER_DATA_DIR = os.path.join(os.getcwd(), 'selenium_user_data')

# --- 函數區 (與之前相同，略) ---
def initialize_driver(headless=True, user_data_dir=None):
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
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR)
    filepath = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    try:
        driver.save_screenshot(filepath)
        print(f"截圖已保存: {filepath}")
    except Exception as e:
        print(f"保存截圖失敗: {e}")

def scroll_page(driver):
    print("模擬人類滾動行為...")
    driver.execute_script("window.scrollTo(0, Math.random() * window.innerHeight);")
    time.sleep(STABILITY_PAUSE_TIME)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
    time.sleep(STABILITY_PAUSE_TIME)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(STABILITY_PAUSE_TIME)
    print("滾動模擬完成。")

def parse_authors(block_elem, driver, title):
    """
    從論文區塊中解析所有作者，並區分有連結和無連結的作者。
    返回一個包含字典（有連結）和字串（無連結）的列表。
    """
    all_authors = []
    
    try:
        # 首先提取所有有超連結的作者信息
        # 選擇器保持不變，選中<a>標籤
        linked_author_elements = block_elem.find_elements(By.CSS_SELECTOR, 'div.rendering a[rel="Person"][href*="/persons/"]')
        
        linked_author_names = []
        for author_link_elem in linked_author_elements:
            try:
                author_span_elem = author_link_elem.find_element(By.TAG_NAME, 'span')
                name = author_span_elem.text.strip()
                url = author_link_elem.get_attribute('href')
                if name and url:
                    all_authors.append({"name": name, "url": url})
                    linked_author_names.append(name) # 記錄這些已提取的名字
            except NoSuchElementException:
                # 如果 <a> 內沒有 <span>，則嘗試直接獲取 <a> 的文本
                name = author_link_elem.text.strip()
                url = author_link_elem.get_attribute('href')
                if name and url:
                    all_authors.append({"name": name, "url": url})
                    linked_author_names.append(name)
            except StaleElementReferenceException:
                pass # 忽略這個錯誤

        # 獲取包含作者信息的整個文本塊 (減去標題和日期等已知部分)
        # 這是一個挑戰，因為沒有一個單獨的元素包裝所有作者。
        # 我們嘗試獲取主要內容 div 的 outerHTML，然後使用正則表達式解析。
        # 更準確的方法可能是獲取所有直接子節點並判斷。
        
        # 更好的方法：獲取包含所有作者信息的 rendering div 的所有子節點
        # 然後過濾掉標題和日期等，只保留作者相關的文本或連結元素
        rendering_div = block_elem.find_element(By.CSS_SELECTOR, 'div.rendering.rendering_researchoutput')
        
        # 獲取所有直接文本和元素節點
        # ChromeDevToolsProtocol (CDP) 可能更適合，但複雜
        # 這裡我們採取一個相對簡單的辦法：獲取整個 rendering_div 的 text
        # 然後從中去除已知的連結作者和日期等，剩下的就是無連結作者。
        full_text = rendering_div.text
        
        # 移除標題
        title_elem = rendering_div.find_element(By.CSS_SELECTOR, 'h3.title a')
        full_text = full_text.replace(title_elem.text.strip(), '').strip()
        
        # 移除已抓取的連結作者
        for name in linked_author_names:
            full_text = full_text.replace(name, '').strip()

        # 移除年份 (假設日期格式為 'YYYY')
        date_match = re.search(r'\b\d{4}\b', full_text)
        if date_match:
            full_text = full_text.replace(date_match.group(0), '').strip()
        
        # 移除其他已知可能干擾的模式，例如 'Computational Science and Its Applications – ICCSA 2024 Workshops, Proceedings.'
        # 這是比較脆弱的，因為它依賴於特定的文本模式
        # 一個更穩健的方法是識別日期 <span class="date">，然後獲取其之前的所有文本內容
        
        # 重新嘗試使用更精確的節點遍歷方法來獲取作者列表
        all_author_nodes_html = driver.execute_script("""
            var block = arguments[0];
            var renderingDiv = block.querySelector('div.rendering.rendering_researchoutput');
            if (!renderingDiv) return "";

            var children = Array.from(renderingDiv.childNodes);
            var authorsHtml = [];
            var foundTitle = false;
            var foundDate = false;

            for (var i = 0; i < children.length; i++) {
                var node = children[i];
                if (node.nodeType === Node.ELEMENT_NODE && node.matches('h3.title')) {
                    foundTitle = true; // 忽略標題
                    continue;
                }
                if (foundTitle) { // 在標題之後開始尋找作者
                    if (node.nodeType === Node.ELEMENT_NODE && node.matches('span.date')) {
                        foundDate = true; // 遇到日期就停止收集作者
                        break;
                    }
                    if (node.nodeType === Node.ELEMENT_NODE && node.matches('a[rel="Person"]')) {
                        // 這是連結作者，我們已經單獨處理了，這裡可以跳過或者用來判斷邊界
                        authorsHtml.push(node.outerHTML);
                    } else if (node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0) {
                        authorsHtml.push(node.textContent.trim());
                    } else if (node.nodeType === Node.ELEMENT_NODE && node.textContent.trim().length > 0) {
                        // 可能是一些無連結的作者被包裹在其他標籤裡，但沒有rel="Person"
                        authorsHtml.push(node.textContent.trim());
                    }
                }
            }
            return authorsHtml.join(' ');
        """, block_elem) # 將 block_elem 傳遞給 JavaScript

        # 現在 all_author_nodes_html 包含了所有在標題和日期之間找到的文本和元素內容
        # 我們需要從中提取無連結的作者
        
        # 將 HTML 字符串重新解析，找出所有不帶連結的作者
        # 使用 BeautifulSoup 會更合適，但為了不引入新庫，我們用正則粗略處理
        
        # 一種更簡單但可能不那麼精確的方式是：
        # 提取 rendering_div 內除了 title, date 之外的所有文本，然後去除 linked_author_names
        full_authors_string = rendering_div.text
        
        # 剔除標題
        if title:
            full_authors_string = full_authors_string.replace(title, '', 1).strip()
        
        # 剔除年份（假設年份就在作者之後，且格式為YYYY）
        date_span = rendering_div.find_elements(By.CSS_SELECTOR, 'span.date')
        if date_span:
            full_authors_string = full_authors_string.replace(date_span[0].text.strip(), '', 1).strip()

        # 剔除有連結的作者
        for name in linked_author_names:
            full_authors_string = full_authors_string.replace(name, '', 1).strip() # 只替換一次，避免重複姓名問題

        # 現在 full_authors_string 理論上只剩下無連結的作者名以及一些分隔符
        # 我們需要將它拆分為個別的作者，並將其添加到 all_authors
        # 假設無連結作者名之間用逗號分隔，且名稱後沒有其他非作者內容
        # 例如: "Liang, K. W., Guo, Y. S., Wang, C. Y., Le, P. T., Putri, W. R., , Chang, P.-C. &amp; , "
        
        # 先清除多餘的逗號和 " &amp; "，然後根據逗號分割
        # 這一步可能需要針對實際輸出進行調試和優化
        cleaned_authors_string = re.sub(r'(,\s*){2,}', ', ', full_authors_string) # 清理多餘逗號
        cleaned_authors_string = cleaned_authors_string.replace('&amp;', '&').replace('&', ',').strip() # 將 & 視為分隔符
        
        # 移除開頭或結尾可能的逗號
        cleaned_authors_string = cleaned_authors_string.strip(',').strip()

        # 分割成無連結作者
        if cleaned_authors_string:
            no_link_authors = [
                author.strip() 
                for author in cleaned_authors_string.split(',') 
                if author.strip() and author.strip() not in linked_author_names
            ]
            for author in no_link_authors:
                all_authors.append(author) # 以字串形式添加無連結作者

    except Exception as e:
        print(f"解析作者時發生錯誤: {e}")

    return all_authors


def scrape_page_data(driver, page_num):
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
            all_authors_list = [] # 現在用這個列表儲存所有作者

            try:
                title_elem = block.find_element(By.CSS_SELECTOR, 'div.result-container h3 a')
                title = title_elem.text.strip()
            except NoSuchElementException:
                pass

            # 調用新的作者解析函數
            all_authors_list = parse_authors(block, driver, title)

            data.append({
                'title': title,
                'authors': all_authors_list # 鍵名改為 'authors'
            })
    except TimeoutException:
        print(f"警告: 頁面 {page_num+1} 等待論文列表超時，當前頁面可能沒有論文或載入失敗。")
        take_screenshot(driver, f"page_{page_num}_timeout")
    except Exception as e:
        print(f"抓取頁面 {page_num+1} 數據時發生錯誤: {e}")
        take_screenshot(driver, f"page_{page_num}_error")
        
    return data

# --- 主函數 (與之前相同) ---
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
        
        # --- 後處理數據，按教授超連結分類論文 ---
        print("\n--- 正在進行數據後處理 (按教授分類論文) ---")
        prof_papers = {}
        for paper in all_papers:
            title = paper['title']
            for author in paper['authors']:
                if isinstance(author, dict) and 'url' in author: # 判斷是有連結的教授
                    prof_url = author['url']
                    prof_name = author['name']
                    
                    if prof_url not in prof_papers:
                        prof_papers[prof_url] = {
                            'name': prof_name, # 記錄教授名字，方便識別
                            'papers': []
                        }
                    prof_papers[prof_url]['papers'].append(title)
        
        # 保存分類後的數據
        prof_output_filename = 'ncu_papers_by_professor.json'
        with open(prof_output_filename, 'w', encoding='utf-8') as f:
            json.dump(prof_papers, f, ensure_ascii=False, indent=4)
        print(f"按教授分類的論文數據已保存到 {prof_output_filename}")


if __name__ == '__main__':
    main()