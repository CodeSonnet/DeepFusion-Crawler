# -*- coding: utf-8 -*-
import time
import json
import os
import random
from DrissionPage import ChromiumPage

# ================= ⚙️ 配置区域 =================
PRODUCT_NAME = "HuaWei P70 "  # 产品名称，用于标记数据来源
SHOP_URLS = [
    "https://item.jd.com/100106087181.html", #华为京东自营店
    "https://item.jd.com/10101253672823.html",# 京联通达旗舰店
    "https://item.jd.com/100160993868.html",   # 中国电信京东自营旗舰店
    "https://item.jd.com/10185204717301.html",  # 福鑫备库小店
    "https://item.jd.com/100169786473.html",   # 京东手机直营旗舰店
    "https://item.jd.com/10100794886722.html", # 领凡手机旗舰店
    "https://item.jd.com/10106555235225.html",# 中企手机旗舰店
    "https://item.jd.com/100183761500.html", # 华为移动京东自营专卖店
]

SCROLL_TIMES = 5000 
JSON_FILE = 'data/jd_HuaWei_P70.json'
# ===============================================

def spider_jd_drain_mode():
    # 初始化
    all_data = []
    unique_ids = set()
    
    # 读取旧数据（断点续传）
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
                all_data.extend(old_data)
                for item in old_data:
                    if 'id' in item: unique_ids.add(item['id'])
            print(f"📂 已加载历史数据: {len(all_data)} 条")
        except: pass

    dp = ChromiumPage()
    dp.listen.start('client.action') # 开启监听
    try:
        for url in SHOP_URLS:
            print(f"\n🚀 启动任务: {url}")
            dp.get(url)
            time.sleep(5)

            # === 1. 打开弹窗 ===
            print("👀 尝试打开评论弹窗...")
            try:
                # 先滚一点，让按钮加载出来
                dp.scroll.down(500)
                time.sleep(random.uniform(2, 4))
                
                # 点击按钮
                btn = dp.ele('text=全部评价') or dp.ele('text=商品评价')
                if btn:
                    btn.click()
                    print("✅ 弹窗已打开")
                else:
                    input("❌ 自动打开失败，请手动点击后回车 >>")
            except:
                input("❌ 发生异常，请手动点击打开后回车 >>")
            
            print("✅ 弹窗已打开！开始爬取...")
            print("💡 提示：运行过程中，随时按【Ctrl + C】可强制停止并保存数据！")
            time.sleep(5)

            # === 2. 循环抓取 ===
            # 这里的 SCROLL_TIMES 只是一个大致的轮次限制
            no_data_rounds = 0
            try:
                for i in range(SCROLL_TIMES):
                    print(f"\r🔄 第 {i+1} 轮 | 总数据: {len(all_data)} | ", end="")

                    # --- [A] 强制滚动修复 (JS注入) ---
                    # 尝试找到京东弹窗的那个滚动容器
                    # 通常它的 class 是 'comment-con' 或者是在 dialog 里的 list
                    try:
                        # 方案1：找到当前最后一条评论，让她进入视野
                        last_item = dp.ele('.comment-item@@-1') # @@-1 表示取最后一个
                        if last_item:
                            last_item.scroll.to_see() 
                        else:
                            # 方案2：如果没找到，尝试全局滚动（应对全屏模式）
                            dp.scroll.down(800)
                    except:
                        pass # 滚不动就算了，你可以手动滚

                    # 给一点时间让数据加载出来
                    time.sleep(3) 

                    # --- [B] 核心：队列清空模式 (Queue Draining) ---
                    # 不再用 wait() 等一个，而是用 steps() 遍历所有积压的包
                    # timeout=1 表示：处理完积压的包后，再多等1秒，如果没有新包就继续
                    packet_count = 0
                    
                    # 🔥 这行代码是解决"手滑太快漏数据"的关键 🔥
                    for packet in dp.listen.steps(timeout=1):
                        try:
                            raw_json = packet.response.body
                            # 检查是否是评论包
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
                                                    # 追评提取
                                                    append_review = ""
                                                    if isinstance(info.get('afterComment'), dict):
                                                        append_review = info['afterComment'].get('content', '')

                                                    clean_item = {
                                                        "platform": "JD",
                                                        "product_name": PRODUCT_NAME,
                                                        "id": cid,
                                                        "content": info.get('commentData', '').replace('\n', ' '),
                                                        "score": int(info.get('commentScore', 0)),
                                                        "date": info.get('commentDate', '未知'),
                                                        "model_sku": info.get('productSpecifications', '异常'),
                                                        "append_content": append_review.replace('\n', ' '),
                                                        "votes": int(info.get('praiseCnt', 0)),
                                                        "images": [p.get('largePicURL', p.get('picURL')) for p in info.get('pictureInfoList', [])]
                                                    }
                                                    
                                                    all_data.append(clean_item)
                                                    unique_ids.add(cid)
                                                    packet_count += 1
                        except:
                            pass
                    
                    # --- 状态显示 ---
                    if packet_count > 0:
                        print(f"⚡ 爆发抓取! 处理了 {packet_count} 条新数据")
                        no_data_rounds = 0
                    else:
                        print(f"等待中... {no_data_rounds}/10", end="")
                        no_data_rounds += 1

                    if no_data_rounds >= 10:
                        print(f"\n🛑 本店数据似乎已抓完 (连续10轮无新包)，正在切换下一家店铺...")
                        break # 跳出当前 for i in range(SCROLL_TIMES) 循环

                    # === 4. 防封核心：动态休眠策略 (保持你的代码) ===
                    if (i + 1) % random.randint(10,15) == 0:
                        long_sleep = random.uniform(30, 60)
                        print(f"\n☕ 触发长休息机制，暂停 {long_sleep:.1f} 秒...")
                        time.sleep(long_sleep)
                    else:
                        short_sleep = random.uniform(8, 15) # 保持你原本的节奏
                        time.sleep(short_sleep)

            except KeyboardInterrupt:
                print("\n🛑 用户强制停止！正在保存数据...")
                break
            except Exception as e:
                print(f"\n❌ 当前店铺发生错误: {e}，跳过并尝试保存...")
                continue

            # === 单个店铺爬完后，立即保存一次 ===
            # 这样如果爬第2家店报错，第1家的数据也已经存下来了
            if not os.path.exists('data'): os.makedirs('data')
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            print(f"\n💾 [存档] 当前总数据量: {len(all_data)} 条")

            # === 店铺切换长休眠 ===
            current_index = SHOP_URLS.index(url)
            if current_index < len(SHOP_URLS) - 1:
                switch_sleep = random.uniform(30, 60)
                print(f"💤 准备前往下一家店铺，休息 {switch_sleep:.1f} 秒...")
                time.sleep(switch_sleep)

    except KeyboardInterrupt:
        print("\n🛑 用户强制停止程序！")
    except Exception as e:
        print(f"\n❌ 发生未知错误: {e}")

    # === 最终保存 ===
    if all_data:
        if not os.path.exists('data'): os.makedirs('data')
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"🎉 全部任务完成！总共保存 {len(all_data)} 条数据至: {JSON_FILE}")
    else:
        print("⚠️ 本次没有抓取到任何数据。")

if __name__ == '__main__':
    spider_jd_drain_mode()