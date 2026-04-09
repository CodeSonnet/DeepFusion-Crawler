# -*- coding: utf-8 -*-
import time
import json
import os
import re
import random
import math
from DrissionPage import ChromiumPage, ChromiumOptions

# ================= ⚙️ 配置区域 =================
PRODUCT_NAME = "真我 GT 7 Pro"  # 产品名称，用于标记数据来源

# 淘宝/天猫商品链接列表
SHOP_URLS = [
    #Redmi K80
    #"https://detail.tmall.com/item.htm?abbucket=9&id=855871434996&mi_id=0000CDiYiHh50GPP9_AeDRylgiOvc4gTWYlYOMSfEH0uh1k&ns=1&priceTId=213e05ef17755801666898544e12e7&skuId=5836368211877&spm=a21n57.1.item.3&utparam=%7B%22aplus_abtest%22%3A%2243ad1fbe7ae504d12c2f94396bc6ef97%22%7D&xxc=taobaoSearch",
    #"https://detail.tmall.com/item.htm?ali_refid=a3_430582_1006%3A2558538047%3AH%3A4w26l6jzY%2FxAqjnyc%2BNzWmX9rGaBn3hp%3Af1f42ebff452b3c39e4e0f029cf085a2&ali_trackid=282_f1f42ebff452b3c39e4e0f029cf085a2&id=920957702342&mi_id=0000ZcOw8b3oG9sJqD_BdcjGpE98oRtwhP4EzgLjMv7ixNU&mm_sceneid=1_0_7367393876_0&skuId=6009134897926&spm=a21n57.1.hoverItem.1&utparam=%7B%22aplus_abtest%22%3A%229dbfdd3920a146b5fbf382cf1dd4d836%22%7D&xxc=ad_ztc",
    #"https://detail.tmall.com/item.htm?abbucket=9&fpChannel=101&fpChannelSig=ae94864cfd8ec7ac8763985be57750fedea38d13&id=861599449488&mi_id=0000m_7XSudpXCOKsDL3IgLpxQzRyacxTENV-lsaiy_50s8&ns=1&skuId=5847817715225&spm=a21n57.1.hoverItem.2&u_channel=bybtqdyh&umpChannel=bybtqdyh&utparam=%7B%22aplus_abtest%22%3A%22dd1df772fc451a51b0f48ee46c829d84%22%7D&xxc=taobaoSearch",
    #"https://detail.tmall.com/item.htm?abbucket=9&id=856717087068&mi_id=0000LM97zWZiKl905lXoKmzvlPRbeGQ4IfWXJckiwG6i3F8&ns=1&priceTId=213e037117755802164237741e0f7b&skuId=6014349265039&spm=a21n57.1.hoverItem.4&utparam=%7B%22aplus_abtest%22%3A%22cd1a28334aa7829b42623511c9a021ce%22%7D&xxc=taobaoSearch",
    # iQOO 15
    #"https://detail.tmall.com/item.htm?ali_refid=a3_430582_1006%3A1104380429%3AH%3ArljAQrgSFsZqU%2FRMoIX%2B%2BQ%3D%3D%3Acf2f12723898ba63fea986290afa54b9&ali_trackid=318_cf2f12723898ba63fea986290afa54b9&fpChannel=101&fpChannelSig=c7e3704e9f6664f6e2c914226fa5c8b99875a513&id=972194079657&mi_id=0000re6YTknGuUNMeVex8BmbK2GkuB9YHDzC3ldStfaOmCw&mm_sceneid=0_0_31676741_0&skuId=6046680492075&spm=a21n57.1.hoverItem.1&utparam=%7B%22aplus_abtest%22%3A%229ecc7a9d60821ff02e20105f34bd38d0%22%7D&xxc=ad_ztc",
    #"https://detail.tmall.com/item.htm?ali_refid=a3_420434_1006%3A1355700140%3AH%3AR25HnSmiPvTGiwM6UkVNJb2Ozm4nW%2FMy%3Ae6d6d82fa593975e5c9263269a79d276&ali_trackid=318_e6d6d82fa593975e5c9263269a79d276&id=974827989996&mi_id=0000Y4VYURRVJd51jGgQERc_zrNAEUoMwlRm-JC6zFUPJkI&mm_sceneid=0_0_1426190081_0&skuId=6211567786733&spm=a21n57.1.hoverItem.2&utparam=%7B%22aplus_abtest%22%3A%22bd753e3a177a57a87f40082d8bb3f2b8%22%7D&xxc=ad_ztc",
    #"https://detail.tmall.com/item.htm?ali_refid=a3_420434_1006%3A1355700140%3AH%3ASgH2dPKbSzf%2FoABshKJ2sWTWcdKaiVbd%3A493abffe9cbba04fa0564948612b0bd4&ali_trackid=318_493abffe9cbba04fa0564948612b0bd4&id=973611503138&mi_id=0000ype4IEO_HpSmxXow-AY8vbtkIDWUOfZdlWxmvLucVDw&mm_sceneid=0_0_1426190081_0&skuId=6212053255178&spm=a21n57.1.hoverItem.4&utparam=%7B%22aplus_abtest%22%3A%2204d8d24ed6d13637dd20686940cd7183%22%7D&xxc=ad_ztc",
    #没爬完"https://detail.tmall.com/item.htm?abbucket=9&fpChannel=101&fpChannelSig=7c7b1b0c29d82644c0540fd5710442d91e6299a3&id=972708634672&mi_id=0000lUxFCOYD50a_cc6qOm2upIUwDsBTSicXuoFUgYq61FM&ns=1&skuId=6212469071093&spm=a21n57.1.hoverItem.8&u_channel=bybtqdyh&umpChannel=bybtqdyh&utparam=%7B%22aplus_abtest%22%3A%2203d177d7bd30ac83ee6ff148dbd7c7fb%22%7D&xxc=taobaoSearch",
    #荣耀 Magic 7 Pro,
    #"https://detail.tmall.com/item.htm?abbucket=9&fpChannel=101&fpChannelSig=78588ca181262d9744ff98867f2ce2527a927090&id=857554269384&mi_id=0000mXVhX1G1eNPllsArFZjvRhgN3SzarWnWbaDNAXudFUE&ns=1&skuId=5665143268886&spm=a21n57.1.hoverItem.1&u_channel=bybtqdyh&umpChannel=bybtqdyh&utparam=%7B%22aplus_abtest%22%3A%22f218c8ae0d133ec100713f0b6e363ac2%22%7D&xxc=taobaoSearch",
    #"https://item.taobao.com/item.htm?abbucket=9&id=993510523300&mi_id=0000wVRb7FQrBrQn3Ls2YIDEjkSEY5QVrb-e6II0xgoICDo&ns=1&priceTId=213e075317756157898294555e1129&skuId=5973116117685&spm=a21n57.1.hoverItem.4&utparam=%7B%22aplus_abtest%22%3A%2264b26e1aa0258994fc88275c51dea065%22%7D&xxc=taobaoSearch",
    #"https://item.taobao.com/item.htm?abbucket=9&id=857433026724&mi_id=00009V6hCAl9bmIGp5_C9NctpE86OBxP7BDjZ5OfN2W1yng&ns=1&priceTId=213e075317756157898294555e1129&skuId=5835387475627&spm=a21n57.1.hoverItem.5&utparam=%7B%22aplus_abtest%22%3A%2273eab142b26ba7421b59f4375944ce2a%22%7D&xxc=taobaoSearch",
    #"https://item.taobao.com/item.htm?abbucket=9&id=862719166593&mi_id=0000PM21zZDvrg4cvsqJKwicipJZGP3qhrgGc2XNvl_XL0s&ns=1&priceTId=213e075317756157898294555e1129&skuId=5685343457585&spm=a21n57.1.hoverItem.7&utparam=%7B%22aplus_abtest%22%3A%22ed98126a0a5adc70699edb73e76da433%22%7D&xxc=taobaoSearch",
    #"https://item.taobao.com/item.htm?abbucket=9&id=990345546327&mi_id=0000U4MUIypAYimtfBTq7EsvVUfbB0FdEUBBiLbQwI4-E4Q&ns=1&priceTId=213e075317756157898294555e1129&skuId=6125191890327&spm=a21n57.1.hoverItem.8&utparam=%7B%22aplus_abtest%22%3A%228cb520bbf8c6d22b6d8296e878b6698f%22%7D&xxc=taobaoSearch",
    #"https://item.taobao.com/item.htm?abbucket=9&id=855481945158&mi_id=00001lxeBA9SRsphIW1pqFehccBOJ_v4IPQOCIXEo3aQ7f4&ns=1&priceTId=213e075317756157898294555e1129&skuId=6156300510497&spm=a21n57.1.hoverItem.10&utparam=%7B%22aplus_abtest%22%3A%220729bdc6f1b6a0c8a5841700db46b7cc%22%7D&xxc=taobaoSearch",
    #"https://detail.tmall.com/item.htm?abbucket=9&id=838582843115&mi_id=0000UofW0fbyKgB02NbB12f_1QNQ-Z9K99VRVJaLfQ0vaE0&ns=1&priceTId=213e075317756157898294555e1129&skuId=5879787064632&spm=a21n57.1.hoverItem.11&utparam=%7B%22aplus_abtest%22%3A%22765d1b27efa7d617aacfc09827c4b6c4%22%7D&xxc=taobaoSearch",
    #真我 GT 7 Pro
    #没爬完"https://detail.tmall.com/item.htm?abbucket=9&id=838577791595&mi_id=0000K6JycvsvjYwhyB3zkH9CazEPrW68sOc0TW9W9fVTxAY&ns=1&priceTId=213e076717756167845427286e1112&skuId=5639845648822&spm=a21n57.1.hoverItem.2&utparam=%7B%22aplus_abtest%22%3A%22840d76d9b22855cb51ff554e5dfa2ddb%22%7D&xxc=taobaoSearch",
    #OnePlus Ace 6T,
    #"https://detail.tmall.com/item.htm?abbucket=9&id=993016602639&mi_id=0000eHVEfn3wqC6VYFj9DDnN0r6xpMyuNvWGLd6utiW9JoQ&ns=1&priceTId=214780b117757382553954571e1113&skuId=5980215096523&spm=a21n57.1.hoverItem.6&utparam=%7B%22aplus_abtest%22%3A%22d09ca1836f9a5c20a1be1fde51c1fedb%22%7D&xxc=taobaoSearch",
    "https://detail.tmall.com/item.htm?abbucket=9&id=994491524076&mi_id=0000M0f9ApC-0guQ2LlnY4HSRuCe0J1NlhxDw5ZtKAB6d6M&ns=1&priceTId=214780b117757382553954571e1113&skuId=6149333410906&spm=a21n57.1.hoverItem.7&utparam=%7B%22aplus_abtest%22%3A%22b2dba1419310b3a550f7d1274b372c4e%22%7D&xxc=taobaoSearch",
    "https://detail.tmall.com/item.htm?ali_refid=a3_420434_1006%3A1646380005%3AH%3Aes%2F9euL6D3Ak%2FBhb5WI85Rj18NxTpMbD%3A4922128aae39175fab75f36671ff68eb&ali_trackid=318_4922128aae39175fab75f36671ff68eb&fpChannel=101&fpChannelSig=56a659dd1add7b066df01293218936c87989e9e0&id=994046639924&maskChannel=bybtrs&mi_id=0000BINra9kQtVkLPs0bhyCf7ovx5xgxcTKY4O-MjZZn4EE&mm_sceneid=0_0_2907870118_0&priceTId=214780b117757382553954571e1113&skuId=6210734042283&spm=a21n57.1.hoverItem.2&u_channel=bybtqdyh&umpChannel=bybtqdyh&utparam=%7B%22aplus_abtest%22%3A%2233a280c2c4521a78324f27f2fcf67ae1%22%7D&xxc=ad_ztc",
    "",
    "",
    "",
] #URL

SCROLL_TIMES = 1000  # 淘宝有效评论通常较少，1000轮绝对够用了
JSON_FILE = 'data/TaoBao/taobao_OnePlus_Ace_6T.json'
USER_DATA_DIR = './Taobao_User_Data'  # 🔥 淘宝专属：用于保存你的登录状态(Cookies)
# ===============================================

def human_like_space_scroll(dp, round_num):
    """
    在评论区抽屉中按空格键下滑评论，模拟真人随机行为以规避反爬虫。
    """
    try:
        # 动态决定本轮按几次空格
        if random.random() < 0.15:
            press_count = random.randint(3, 4)
        else:
            press_count = random.randint(1, 2)

        for j in range(press_count):
            # 30% 概率先做鼠标微移
            if random.random() < 0.30:
                try:
                    offset_x = random.randint(-80, 80)
                    offset_y = random.randint(-40, 40)
                    dp.actions.move(offset_x, offset_y, duration=random.uniform(0.2, 0.6))
                    time.sleep(random.uniform(0.3, 0.8))
                except:
                    pass

            # 按空格键
            dp.actions.key_down('Space')
            hold_time = max(0.05, random.gauss(0.12, 0.04))
            time.sleep(hold_time)
            dp.actions.key_up('Space')

            # 按键间隔
            if j < press_count - 1:
                gap = max(0.4, random.gauss(1.5, 0.6))
                time.sleep(gap)

        # 8% 概率回看（按上方向键再补空格）
        if random.random() < 0.08:
            time.sleep(random.uniform(0.5, 1.2))
            dp.actions.key_down('ArrowUp')
            time.sleep(max(0.05, random.gauss(0.10, 0.03)))
            dp.actions.key_up('ArrowUp')
            time.sleep(random.uniform(0.8, 1.5))
            dp.actions.key_down('Space')
            time.sleep(max(0.05, random.gauss(0.12, 0.04)))
            dp.actions.key_up('Space')

        # 12% 概率长停留（模拟阅读评论）
        if random.random() < 0.12:
            read_time = random.uniform(3.0, 8.0)
            print(f"  [Read] {read_time:.1f}s...", end="")
            time.sleep(read_time)

        # 每隔约30轮做一次走神停顿
        if round_num > 0 and round_num % random.randint(25, 35) == 0:
            distract_time = random.uniform(5.0, 15.0)
            print(f"\n  [Distract] {distract_time:.1f}s...")
            time.sleep(distract_time)

    except Exception as e:
        try:
            dp.scroll.down(random.randint(300, 600))
        except:
            pass


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
    dp.get("https://www.tmall.com/")
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

                    # --- [A] 在评论抽屉中按空格键模拟滚动（真人行为）---
                    human_like_space_scroll(dp, i)

                    # 每次滚动后的基础等待（正态分布，均值3秒，标准差1秒）
                    base_wait = max(1.5, random.gauss(3.0, 1.0))
                    time.sleep(base_wait) 

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

                                            # 解析评分 (rateType: 1好评->5分, 0中评->3分, -1差评->1分)
                                            rate_type = str(item.get('rateType', '1'))
                                            if rate_type == '1':
                                                score = 5
                                            elif rate_type == '0':
                                                score = 3
                                            elif rate_type == '-1':
                                                score = 1
                                            else:
                                                score = 5

                                            # 4. 组装纯净数据 (映射你之前给我的真实天猫字段名)
                                            clean_item = {
                                                "platform": "Taobao/Tmall",
                                                "product_name": PRODUCT_NAME,
                                                "id": cid,
                                                "content": item.get('feedback', item.get('rateContent', '')).replace('\n', ' '),
                                                "score": score,
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
                    if no_data_rounds >= 50:
                        print(f"\n🛑 本店数据似乎已抓完 (连续50轮无新包)，正在切换下一家店铺...")
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