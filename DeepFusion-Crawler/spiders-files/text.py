# -*- coding: utf-8 -*-
import time
import json
import os
import random
from DrissionPage import ChromiumPage

# ================= ⚙️ 配置区域 =================
# 1. 替换为你要爬的手机链接
PRODUCT_URL = "https://item.jd.com/100209268189.html" 

# 2. 手动填入手机名称 (因为JSON里没有这个字段，需要自己补全)
PRODUCT_NAME = "iPhone 17 Pro Max"

# 3. 爬多少次 (每次滚动加载约10条)
SCROLL_TIMES = 5000 

# 4. 保存文件名
JSON_FILE = 'data/jd_iphone17_clean.json'
# ===============================================

def spider_jd_floors_structure():
    # 1. 启动浏览器
    dp = ChromiumPage()
    print(f"🚀 启动任务: {PRODUCT_NAME}")
    dp.get(PRODUCT_URL)
    time.sleep(2)

    # 2. 开启监听 (监听包含 'client.action' 的数据包)
    dp.listen.start('client.action')

    # 3. 打开评论弹窗
    print("👀 正在打开评论弹窗...")
    if dp.ele('text=全部评价'):
        dp.ele('text=全部评价').click()
    elif dp.ele('text=商品评价'):
        dp.ele('text=商品评价').click()
    else:
        input("❌ 未找到按钮，请手动点击【全部评价】打开弹窗，然后按回车 >>")

    print("✅ 弹窗已打开，开始抓取...")
    time.sleep(2)
    
    all_data = []
    unique_ids = set() # 防重

    # 4. 循环滚动并抓取
    for i in range(SCROLL_TIMES):
        print(f"🔄 [第 {i+1} 次] 滚动加载中...")

        # --- 动作：模拟鼠标在弹窗中间滚动 (触发加载) ---
        try:
            # 这一步是为了让京东服务器发包
            rect = dp.rect
            dp.actions.move_to(x=rect.width/2, y=rect.height/2).scroll(800)
        except:
            pass

        # --- 核心：等待并解析数据包 ---
        res = dp.listen.wait(timeout=3)
        
        if res:
            try:
                # 获取 JSON
                raw_json = res.response.body
                
                # 🔍 针对你提供的 JSON 结构进行精准定位
                # 路径: result -> floors -> [遍历] -> mId=='commentlist-list' -> data
                if isinstance(raw_json, dict) and 'result' in raw_json and 'floors' in raw_json['result']:
                    
                    floors = raw_json['result']['floors']
                    
                    for floor in floors:
                        # 只找 "commentlist-list" 这一层，其他层是标签或头部图片，不需要
                        if floor.get('mId') == 'commentlist-list':
                            
                            # 拿到 data 列表
                            comment_list = floor.get('data', [])
                            
                            current_batch = 0
                            for item in comment_list:
                                # 确保里面有 commentInfo
                                if 'commentInfo' in item:
                                    info = item['commentInfo']
                                    cid = info.get('commentId')

                                    # 去重
                                    if cid in unique_ids:
                                        continue

                                    # ✅ 提取你指定的6个字段
                                    clean_item = {
                                        "platform": "JD",
                                        "product_name": PRODUCT_NAME,
                                        "content": info.get('commentData', '').replace('\n', ' '), # 对应 commentData
                                        "score": int(info.get('commentScore', 0)), # 对应 commentScore
                                        "date": info.get('commentDate', '未知'),   # 对应 commentDate
                                        "model_sku": info.get('productSpecifications', '未知') # 对应 productSpecifications
                                    }
                                    
                                    all_data.append(clean_item)
                                    unique_ids.add(cid)
                                    current_batch += 1
                            
                            if current_batch > 0:
                                print(f"   + 成功抓取 {current_batch} 条 (示例: {clean_item['content'][:10]}...)")

            except Exception as e:
                # 可能会监听到其他无关数据包，报错是正常的，忽略即可
                pass
        
        # 随机等待，防止滑太快被封
        time.sleep(random.uniform(1.5, 3))

    # 5. 保存
    if not os.path.exists('data'): os.makedirs('data')
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n🎉 抓取结束！共 {len(all_data)} 条数据，保存在 {JSON_FILE}")

if __name__ == '__main__':
    spider_jd_floors_structure()