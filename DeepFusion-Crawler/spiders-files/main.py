# -*- coding: utf-8 -*-
import time
import json
import os
import random
from DrissionPage import ChromiumPage

# ================= ⚙️ 配置区域 =================
# 1. 商品名称 (用于保存文件名和数据字段)
PRODUCT_NAME = "iPhone 17 Pro "

# 2. 多店铺链接列表 (请在这里填入该手机在不同店铺的链接)
SHOP_URLS = [
    "https://item.jd.com/100209268189.html",  # 店铺 A 
    "https://item.jd.com/100209267859.html",  # 店铺 B 
    "https://item.jd.com/100209286837.html", # 店铺 C
]

# 3. 每个店铺爬取多少次 (下滑次数)
SCROLL_TIMES = 5000 

# 4. 保存文件路径 (所有店铺的数据都会存到这个文件里)
JSON_FILE = 'data/jd_iphone17_pro.json'
# ===============================================

def spider_jd_safe_stop():
    # --- 0. 初始化数据 (实现断点续传/多店聚合的核心) ---
    all_data = []
    unique_ids = set()

    # 如果文件已存在，先读取旧数据，防止覆盖
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                all_data.extend(old_data)
                # 提取旧数据的ID放入去重集合
                for item in old_data:
                    # 注意：为了能去重，我们需要在下面的 clean_item 里多存一个 'id' 字段
                    # 如果旧数据里没 id，就跳过
                    if 'id' in item:
                        unique_ids.add(item['id'])
            print(f"📂 已加载历史数据: {len(all_data)} 条，将继续追加新数据...")
        except Exception as e:
            print(f"⚠️ 读取旧文件失败: {e}，将重新开始...")

    dp = ChromiumPage()
    
    # 开启监听 (只需要开启一次)
    dp.listen.start('client.action')

    # === 外层循环：遍历所有店铺 ===
    for url_index, url in enumerate(SHOP_URLS):
        print(f"\n🚀 [第 {url_index + 1}/{len(SHOP_URLS)} 家店铺] 启动任务: {url}")
        
        try:
            dp.get(url)
            # 这里的等待时间保留你原本的习惯
            time.sleep(5)

            # 打开弹窗
            print("👀 正在打开评论弹窗...")
            try:
                # 先简单滚一下背景
                dp.scroll.down(random.randint(400, 800))
                time.sleep(random.uniform(2, 4))

                if dp.ele('text=全部评价'):
                    dp.ele('text=全部评价').click()
                elif dp.ele('text=商品评价'):
                    dp.ele('text=商品评价').click()
                else:
                    print("❌ 未找到按钮，请手动点击！")
                    time.sleep(5) 
            except:
                pass

            print("✅ 弹窗已打开！开始爬取...")
            print("💡 提示：运行过程中，随时按【Ctrl + C】可强制停止并保存数据！")
            time.sleep(2)
            
            no_data_count = 0 # 计数器：连续多少次没抓到数据

            # === 内层循环：你原本的爬取逻辑 ===
            for i in range(SCROLL_TIMES):
                print(f"\r🔄 [店铺{url_index+1}] 第 {i+1} 次滚动... (总数据: {len(all_data)} 条)", end="")

                # 1. 模拟滚动
                try:
                    rect = dp.rect
                    dp.actions.move_to(x=rect.width/2, y=rect.height/2).scroll(random.randint(800, 1500))
                except:
                    pass

                # 2. 等待数据 (保持你原本的逻辑)
                res = dp.listen.wait(timeout=random.uniform(3, 5)) # 这里稍微改小一点timeout，主要靠sleep防封
                
                found_new_data = False
                batch_count = 0

                if res:
                    try:
                        raw_json = res.response.body
                        if isinstance(raw_json, dict) and 'result' in raw_json and 'floors' in raw_json['result']:
                            floors = raw_json['result']['floors']
                            for floor in floors:
                                if floor.get('mId') == 'commentlist-list':
                                    comment_list = floor.get('data', [])
                                    for item in comment_list:
                                        if 'commentInfo' in item:
                                            info = item['commentInfo']
                                            cid = info.get('commentId')
                                            
                                            if cid not in unique_ids:
                                                # --- 核心：追评提取逻辑 ---
                                                append_review = ""
                                                after_obj = info.get('afterComment')
                                                if isinstance(after_obj, dict):
                                                    append_review = after_obj.get('content', '')
                                                    # 有些追评可能是系统自动生成的“用户未填写”，可以根据需要过滤，这里先保留

                                                # ✅ 提取你指定的7个字段
                                                clean_item = {
                                                    "platform": "JD",
                                                    "product_name": PRODUCT_NAME,
                                                    # 增加 id 字段用于后续去重，不影响数据库入库
                                                    "id": cid, 
                                                    "content": info.get('commentData', '').replace('\n', ' '),
                                                    "score": int(info.get('commentScore', 0)),
                                                    "date": info.get('commentDate', '未知'),
                                                    "model_sku": info.get('productSpecifications', '未知'),
                                                    "append_content": append_review.replace('\n', ' ')
                                                }
                                        
                                                all_data.append(clean_item)
                                                unique_ids.add(cid)
                                                batch_count += 1
                                                found_new_data = True
                    except Exception as e:
                        pass
                
                # 3. 智能刹车逻辑
                if found_new_data:
                    no_data_count = 0
                    print("   ✅ 抓到了新数据！")
                else:
                    no_data_count += 1
                    print(f"   ⚠️ 本次未抓到新数据 (连续空跑 {no_data_count}/5 次)")
                
                # 如果连续 5 次没数据，判定到底
                if no_data_count >= 5:
                    print(f"\n🛑 本店已抓取完毕 ，准备切换下一家...")
                    break

                # === 4. 防封核心：动态休眠策略 (保持你的代码) ===
                if (i + 1) % random.randint(10,15) == 0:
                    long_sleep = random.uniform(30, 60)
                    print(f"\n☕ 触发长休息机制，暂停 {long_sleep:.1f} 秒...")
                    time.sleep(long_sleep)
                else:
                    short_sleep = random.uniform(8, 15) # 保持你原本的节奏
                    time.sleep(short_sleep)

            # === 单个店铺爬完后，立即保存一次 ===
            # 这样如果爬第2家店报错，第1家的数据也已经存下来了
            if not os.path.exists('data'): os.makedirs('data')
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            print(f"\n💾 [存档] 当前总数据量: {len(all_data)} 条")

            # === 店铺切换长休眠 ===
            if url_index < len(SHOP_URLS) - 1:
                switch_sleep = random.uniform(30, 60)
                print(f"💤 准备前往下一家店铺，休息 {switch_sleep:.1f} 秒...")
                time.sleep(switch_sleep)

        except KeyboardInterrupt:
            print("\n🛑 用户强制停止！正在保存数据...")
            break
        except Exception as e:
            print(f"\n❌ 当前店铺发生错误: {e}，跳过并尝试保存...")
            continue

    # === 最终保存 ===
    if all_data:
        if not os.path.exists('data'): os.makedirs('data')
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"🎉 全部任务完成！总共保存 {len(all_data)} 条数据至: {JSON_FILE}")
    else:
        print("⚠️ 本次没有抓取到任何数据。")

if __name__ == '__main__':
    spider_jd_safe_stop()