# -*- coding: utf-8 -*-
import time
import json
import os
import re
import random
from DrissionPage import ChromiumPage, ChromiumOptions

# ================= ⚙️ 配置区域 =================
PRODUCT_NAME = ""  # 产品名称，用于标记数据来源

# 淘宝/天猫商品链接列表
SHOP_URLS = [] #URL

SCROLL_TIMES = 1000  # 淘宝有效评论通常较少，1000轮绝对够用了
JSON_FILE = 'data/taobao_HuaWei_P70.json'
USER_DATA_DIR = './Taobao_User_Data'  # 🔥 淘宝专属：用于保存你的登录状态(Cookies)
# ===============================================

def spider_taobao_drain_mode():
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

    # --- 0. 启动浏览器并加载用户环境 ---
    co = ChromiumOptions()
    co.set_user_data_path(USER_DATA_DIR)
    dp = ChromiumPage(co)
    
    # --- 1. 强制登录检查环节 ---
    print("\n🔐 [安全防封] 正在前往淘宝首页校验登录状态...")
    dp.get("https://www.taobao.com")
    print("\n" + "="*50)
    print("🛑 请观察弹出的浏览器窗口！")
    print("👉 如果你还没有登录，请立刻【手动扫码登录】！")
    print("👉 淘宝风控极严，不登录绝对抓不到数据！")
    print("✅ 确认登录成功（能看到自己淘宝昵称）后，请在下方按【回车键】继续...")
    print("="*50)
    input(">> 等待操作，按回车正式开始...")

    # 开启监听淘宝核心评价接口
    dp.listen.start('mtop.taobao.rate.detaillist.get') 
    
    try:
        for url in SHOP_URLS:
            print(f"\n🚀 启动任务: {url}")
            dp.get(url)
            time.sleep(5)

            # === 2. 打开评价弹窗/页面 ===
            print("👀 尝试打开评价区域...")
            try:
                # 淘宝的评价按钮通常需要稍微往下拉一点才会浮现
                dp.scroll.down(500)
                time.sleep(random.uniform(2, 4))
                
                # 匹配天猫/淘宝常见的评价按钮文本
                btn = dp.ele('text:评价') or dp.ele('text:累计评价') or dp.ele('text:宝贝评价')
                if btn:
                    btn.click()
                    print("✅ 评价界面已打开")
                else:
                    input("❌ 自动打开失败，请在页面上手动点击【评价】后回车 >>")
            except:
                input("❌ 发生异常，请手动点击打开评价后回车 >>")
            
            print("✅ 准备开始抓取！(随时按 Ctrl+C 可跳过当前店铺)")
            time.sleep(4)

            # === 3. 循环抓取 (队列清空模式) ===
            no_data_rounds = 0
            
            try:
                for i in range(SCROLL_TIMES):
                    print(f"\r🔄 第 {i+1} 轮 | 库中总数: {len(all_data)} | ", end="")

                    # --- [A] 强制向下滚动触发加载 ---
                    try:
                        # 淘宝评价一般是瀑布流，直接全局滚动即可
                        dp.scroll.down(random.randint(600, 1000))
                    except:
                        pass

                    time.sleep(random.uniform(2, 4)) 

                    # --- [B] 核心：队列清空模式与 JSONP 解包 ---
                    packet_count = 0
                    
                    for packet in dp.listen.steps(timeout=1):
                        try:
                            raw_body = packet.response.body
                            json_str = ""
                            
                            # 淘宝的数据被包裹在 mtopjsonp(...) 中，需要正则提取
                            if isinstance(raw_body, str):
                                match = re.search(r'mtopjsonp\d+\((.*)\)', raw_body, re.DOTALL)
                                if match:
                                    json_str = match.group(1)
                                else:
                                    json_str = raw_body 
                            elif isinstance(raw_body, dict):
                                json_str = json.dumps(raw_body)
                                
                            if json_str:
                                data = json.loads(json_str)
                                
                                # 定位评价列表数据
                                if 'data' in data and 'rateList' in data['data']:
                                    rate_list = data['data']['rateList']
                                    
                                    for item in rate_list:
                                        cid = str(item.get('id', ''))
                                        
                                        if cid and cid not in unique_ids:
                                            # 1. 提取图片列表，补全 https:
                                            pic_list = item.get('feedPicPathList', [])
                                            full_pic_list = ["https:" + pic if pic.startswith("//") else pic for pic in pic_list]
                                            
                                            # 2. 提取点赞数
                                            interact_info = item.get('interactInfo', {})
                                            like_count = int(interact_info.get('likeCount', 0))
                                            
                                            # 3. 提取追评 (天猫通常在 appendFeed 里面)
                                            append_review = ""
                                            append_obj = item.get('appendComment') or item.get('appendFeed')
                                            if isinstance(append_obj, dict):
                                                append_review = append_obj.get('content', '') or append_obj.get('feedback', '')

                                            # 4. 组装纯净数据 (映射你之前给我的真实天猫字段名)
                                            clean_item = {
                                                "platform": "Taobao/Tmall",
                                                "product_name": PRODUCT_NAME,
                                                "id": cid,
                                                "content": item.get('feedback', item.get('rateContent', '')).replace('\n', ' '),
                                                "score": 5, # 淘宝现在普遍弱化了1-5打分，默认给好评权重
                                                "date": item.get('feedbackDate', item.get('rateDate', '未知')),
                                                "model_sku": item.get('skuValueStr', item.get('auctionSku', '未知')),
                                                "append_content": append_review.replace('\n', ' '),
                                                "votes": like_count,
                                                "images": full_pic_list,
                                                "reply": item.get('reply', '')
                                            }
                                            
                                            all_data.append(clean_item)
                                            unique_ids.add(cid)
                                            packet_count += 1
                        except Exception as e:
                            pass
                    
                    # --- 状态显示与智能刹车 ---
                    if packet_count > 0:
                        print(f"⚡ 爆发抓取! 处理了 {packet_count} 条新数据")
                        no_data_rounds = 0 # 重置计数器
                    else:
                        print(f"等待中...")
                        no_data_rounds += 1
                        
                    # 淘宝评论很容易到底，连续5轮（约1分钟）无数据就切换
                    if no_data_rounds >= 5:
                        print(f"\n🛑 本店数据似乎已抓完 (连续15轮无新包)，正在切换下一家店铺...")
                        break

                    # --- [C] 防封核心：动态休眠策略 ---
                    if (i + 1) % random.randint(10, 15) == 0:
                        long_sleep = random.uniform(30, 60)
                        print(f"\n☕ 触发长休息机制，暂停 {long_sleep:.1f} 秒...")
                        time.sleep(long_sleep)
                    else:
                        short_sleep = random.uniform(5, 10) 
                        time.sleep(short_sleep)

            except KeyboardInterrupt:
                print("\n🛑 用户强制停止当前店铺！正在保存数据...")
                break
            except Exception as e:
                print(f"\n❌ 当前店铺发生错误: {e}，跳过并尝试保存...")
                continue

            # === 单个店铺爬完后存档 ===
            if not os.path.exists('data'): os.makedirs('data')
            with open(JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, ensure_ascii=False, indent=4)
            print(f"\n💾 [存档] 当前淘宝总数据量: {len(all_data)} 条")

            # === 店铺切换长休眠 ===
            current_index = SHOP_URLS.index(url)
            if current_index < len(SHOP_URLS) - 1:
                switch_sleep = random.uniform(20, 45)
                print(f"💤 准备前往下一家店铺，休息 {switch_sleep:.1f} 秒...")
                time.sleep(switch_sleep)

    except KeyboardInterrupt:
        print("\n🛑 用户强制停止全局程序！")
    except Exception as e:
        print(f"\n❌ 发生未知错误: {e}")

    # === 最终保存 ===
    if all_data:
        if not os.path.exists('data'): os.makedirs('data')
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)
        print(f"🎉 淘宝任务全部完成！总共保存 {len(all_data)} 条数据至: {JSON_FILE}")
    else:
        print("⚠️ 本次没有抓取到任何数据。")

if __name__ == '__main__':
    spider_taobao_drain_mode()