# -*- coding: utf-8 -*-
import time
import json
import os
import random
from DrissionPage import ChromiumPage

# ================= ⚙️ 配置区域 =================
PRODUCT_URL = "https://item.jd.com/100209268189.html" 
PRODUCT_NAME = "iPhone 17 Pro Max"
SCROLL_TIMES = 5000  # 设置大点没关系，反正会自动停
JSON_FILE = 'data/jd_iphone17_safe.json'
# ===============================================

def spider_jd_safe_stop():
    dp = ChromiumPage()
    print(f"🚀 启动任务: {PRODUCT_NAME}")
    dp.get(PRODUCT_URL)
    time.sleep(5)

    # 监听
    dp.listen.start('client.action')

    # 打开弹窗
    print("👀 正在打开评论弹窗...")
    try:
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

    print("✅ 弹窗已打开！")
    print("💡 提示：运行过程中，随时按【Ctrl + C】可强制停止并保存数据！")
    time.sleep(2)
    
    all_data = []
    unique_ids = set()
    no_data_count = 0 # 计数器：连续多少次没抓到数据

    try:
        # === 循环开始 (包裹在 try 里面) ===
        for i in range(SCROLL_TIMES):
            print(f"🔄 [第 {i+1} 次] 滚动中... (已抓取: {len(all_data)} 条)")

            # 1. 模拟滚动
            try:
                rect = dp.rect
                # 鼠标在屏幕中心附近轻微抖动
                dp.actions.move_to(x=rect.width/2 + random.randint(-20,20), y=rect.height/2 + random.randint(-20,20))
                dp.actions.scroll(random.randint(800, 1500))
            except:
                pass

            # 2. 等待数据
            res = dp.listen.wait(timeout=5)
            
            # 标记本轮是否抓到新数据
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
                                            # 检查是否存在 afterComment 且不为空
                                            after_obj = info.get('afterComment')
                                            if isinstance(after_obj, dict):
                                                # 获取追评内容，默认为空字符串
                                                append_review = after_obj.get('content', '')
                                                # 有些追评可能是系统自动生成的“用户未填写”，可以根据需要过滤，这里先保留

                                            # ✅ 提取你指定的7个字段
                                            clean_item = {
                                                "platform": "JD",
                                                "product_name": PRODUCT_NAME,
                                                "content": info.get('commentData', '').replace('\n', ' '), # 对应 commentData
                                                "score": int(info.get('commentScore', 0)), # 对应 commentScore
                                                "date": info.get('commentDate', '未知'),   # 对应 commentDate
                                                "model_sku": info.get('productSpecifications', '未知'), # 对应 productSpecifications
                                                "append_content": append_review.replace('\n', ' ')# 对应 appendCommentData
                                            }
                                    
                                            all_data.append(clean_item)
                                            unique_ids.add(cid)
                                            batch_count += 1
                                            found_new_data = True
                except Exception as e:
                    # 忽略解析错误（可能是无关数据包）
                    pass
            
            # 3. 智能刹车逻辑
            if found_new_data:
                no_data_count = 0 # 重置计数器
                print("   ✅ 抓到了新数据！")
            else:
                no_data_count += 1
                print(f"   ⚠️ 本次未抓到新数据 (连续空跑 {no_data_count}/5 次)")
            
            # 如果连续 5 次没数据，或者 15秒内都没新数据，说明到底了
            if no_data_count >= 5:
                print("\n🛑 连续 5 次未获取新数据，判定已到达底部，自动停止！")
                break

            # === 4.防封核心：动态休眠策略 ===
        
            # 策略A：每抓 10-15 页，来一次“大休息”（模拟人看累了歇会儿）

            if (i + 1) % random.randint(10,15) == 0:
                long_sleep = random.uniform(30, 90)
                print(f"   ☕ 触发长休息机制，暂停 {long_sleep:.1f} 秒...")
                time.sleep(long_sleep)
            else:
                # 策略B：常规页面的慢速阅读（8-20秒）
                short_sleep = random.uniform(8, 20)
                #print(f"   ⏳ 模拟阅读，暂停 {short_sleep:.1f} 秒...")
                time.sleep(short_sleep)
            

    except KeyboardInterrupt:
        # === 这就是你要的功能：按 Ctrl+C 触发这里 ===
        print("\n\n🛑 用户手动停止 (Ctrl+C)！正在紧急保存数据...")

    except Exception as e:
        print(f"\n❌ 发生意外错误: {e}，正在尝试保存...")

    # === 保存数据 (无论怎么退出的，都会执行这里) ===
    if all_data:
        if not os.path.exists('data'): os.makedirs('data')
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"🎉 成功保存 {len(all_data)} 条数据至: {JSON_FILE}")
    else:
        print("⚠️ 本次没有抓取到任何数据。")

if __name__ == '__main__':
    spider_jd_safe_stop()