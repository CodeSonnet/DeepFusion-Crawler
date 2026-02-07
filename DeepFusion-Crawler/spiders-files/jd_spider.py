import time
import json
import random
import os
import pandas as pd  # 引入强大的数据处理库
from selenium import webdriver
from selenium.webdriver.common.by import By

# --- 配置区域 ---
# 模拟真实浏览器，防止被京东识别为机器人
options = webdriver.ChromeOptions()
options.add_argument('--disable-blink-features=AutomationControlled')
# 隐藏 "Chrome正在受到自动软件的控制" 提示
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

def start_crawler():
    # 1. 准备工作：确保 data 文件夹存在
    if not os.path.exists('data'):
        os.makedirs('data')
        print("✅ 已自动创建 data 文件夹")

    # 2. 读取我们要爬的商品列表
    try:
        # 如果 seed_products.json 在上一级目录，这里要做兼容
        config_path = 'seed_products.json' 
        if not os.path.exists(config_path) and os.path.exists('../seed_products.json'):
            config_path = '../seed_products.json'
            
        with open(config_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
    except FileNotFoundError:
        print("❌ 错误：找不到 seed_products.json 文件！请确认它在正确的位置。")
        return

    # 3. 启动浏览器
    print("🚀 启动浏览器中...")
    driver = webdriver.Chrome(options=options)
    
    # 用于临时存储所有爬取到的数据
    all_comments = []

    for product in products:
        print(f"\n------ 正在爬取: {product['product_name']} ------")
        driver.get(product['jd_url'])
        
        # --- 关键：人工干预时间 ---
        # 京东有时会弹出登录窗口，这里留给你15秒手动扫码或关掉弹窗
        print("⏳ 等待页面加载... (如果你看到登录弹窗，请手动关掉或快速扫码，你有15秒时间)")
        time.sleep(15) 

        # 4. 模拟点击“商品评价”标签
        try:
            # 尝试点击“商品评价”按钮，定位更精准
            comment_tab = driver.find_element(By.XPATH, "//li[@data-anchor='#comment']")
            comment_tab.click()
            print("✅ 已点击‘商品评价’标签")
            time.sleep(2)
        except:
            print("⚠️ 未点击评价标签，可能已自动跳转或页面结构改变，尝试直接滚动")

        # 5. 模拟人手滚动页面 (慢慢滚，让数据加载出来)
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {i/3 + 0.3});")
            time.sleep(random.uniform(1, 2))

        # 6. 抓取评论列表
        # 京东评论区的 class 名字通常是 comment-item
        comments = driver.find_elements(By.CLASS_NAME, 'comment-item')
        print(f"👀 本页发现 {len(comments)} 条评论，开始解析...")
        
        for item in comments:
            try:
                # 提取内容
                content_ele = item.find_element(By.CLASS_NAME, 'comment-con')
                content = content_ele.text.replace('\n', ' ') # 去掉换行符
                
                # 尝试提取时间 (京东的时间通常在 order-info 或 comment-time 类似结构里，这里做个通用尝试)
                # 这里的 class 可能会变，如果抓不到也没关系，先保证代码不崩
                try:
                    date_str = item.find_element(By.CLASS_NAME, 'order-info').text
                except:
                    date_str = "未知时间"

                # 对应《数据库结构.pdf》里的字段
                data = {
                    "product_id": product.get('sku_id', 'unknown'), # 从json里拿SKU
                    "product_name": product['product_name'],
                    "platform": "jd",
                    "content": content,
                    "raw_info": date_str, # 暂时把时间和其他信息存在这里
                    "crawl_time": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                all_comments.append(data)
                print(f"   [成功] {content[:15]}...")
            except Exception as e:
                # 某一条出错了跳过，不要卡死
                continue
        
        time.sleep(random.uniform(2, 4))

    driver.quit()
    print("\n✅ 爬取结束，浏览器已关闭。")

    # 7. 保存数据到 CSV (这才是重点！)
    if all_comments:
        df = pd.DataFrame(all_comments)
        # encoding='utf-8_sig' 是为了防止 Excel 打开中文乱码
        save_path = 'data/jd_comments.csv'
        df.to_csv(save_path, index=False, encoding='utf-8_sig')
        print(f"🎉 成功！数据已保存到: {os.path.abspath(save_path)}")
        print("💡 你现在可以去 data 文件夹里双击打开这个 CSV 文件查看成果了！")
    else:
        print("⚠️ 本次没有抓取到任何数据，请检查网络或页面是否弹出了验证码。")

if __name__ == "__main__":
    start_crawler()