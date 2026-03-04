import time
import json
import random
import os
from DrissionPage import ChromiumPage

# ================= 🛠️ 配置区域 =================
PRODUCT_URL = "https://item.jd.com/100209268189.html"
SCROLL_TIMES = 50 
JSON_FILE = 'data/jd_blind_scroll.json'
# ===============================================

def spider_jd_blind_scroll():
    dp = ChromiumPage()
    print("🚀 浏览器启动...")
    dp.get(PRODUCT_URL)
    time.sleep(2)

    # --- 1. 打开评论弹窗 ---
    print("👀 正在打开评论弹窗...")
    dp.scroll.down(200) # 先滚一点背景
    
    # 点击打开
    if dp.ele('text=全部评价'):
        dp.ele('text=全部评价').click()
    elif dp.ele('text=商品评价'):
        dp.ele('text=商品评价').click()
    else:
        input("❌ 没找到按钮，请手动点击打开评论弹窗，然后按回车 >>")

    print("✅ 弹窗已打开！准备开始暴力滚动...")
    time.sleep(2)

    # --- 2. 开启监听 ---
    dp.listen.start('jd.com') 
    all_clean_data = [] 

    # --- 3. 循环滚动 (盲滚模式) ---
    for i in range(SCROLL_TIMES):
        print(f"🔄 [第 {i+1} 次] 鼠标强制滚动中...")

        # === 🔥 核心修改：放弃找元素，直接移到屏幕中心滚 ===
        try:
            # 1. 把鼠标移动到屏幕正中间 (x=窗口宽的一半, y=窗口高的一半)
            # 大部分弹窗都在正中间，所以这招百试百灵
            rect = dp.rect # 获取窗口大小
            center_x = rect.width / 2
            center_y = rect.height / 2
            
            # 移动鼠标
            dp.actions.move_to(x=center_x, y=center_y)
            
            # 2. 疯狂向下滚轮
            # 参数大一点，确保能触发加载
            dp.actions.scroll(1000) 
            
        except Exception as e:
            print(f"   ⚠️ 鼠标操作异常: {e}")

        # === 4. 捕获数据 (解析逻辑不变) ===
        # 等待数据包
        res = dp.listen.wait(timeout=3)
        
        if res:
            try:
                raw_data = res.response.body
                # 检查是不是 floor 结构
                if isinstance(raw_data, dict) and 'result' in raw_data and 'floors' in raw_data['result']:
                    floors = raw_data['result']['floors']
                    for floor in floors:
                        # 只要 data 是列表且里面有 commentInfo，就认为是评论
                        if floor.get('data') and isinstance(floor['data'], list):
                            current_batch = 0
                            for item in floor['data']:
                                if 'commentInfo' in item:
                                    info = item['commentInfo']
                                    
                                    # 提取数据
                                    clean_item = {
                                        "nickname": info.get('userNickName', '匿名'),
                                        "score": info.get('commentScore', '0'), 
                                        "content": info.get('commentData', '').replace('\n', ' '), # 这里是你指出的正确字段
                                        "date": info.get('commentDate', '未知'), 
                                        "model": info.get('productSpecifications', '未知'),
                                        "images": [p.get('largePicURL', p.get('picURL')) for p in info.get('pictureInfoList', [])]
                                    }
                                    
                                    # 去重
                                    # 用 commentId 做唯一标识，防止重复存
                                    cid = info.get('commentId')
                                    # 检查这个 ID 是否已经在列表里了
                                    is_exist = False
                                    for exist_item in all_clean_data:
                                        if exist_item.get('id') == cid:
                                            is_exist = True
                                            break
                                    
                                    if not is_exist:
                                        # 为了方便去重，把ID先加上，最后保存时如果不需要可以删掉
                                        clean_item['id'] = cid 
                                        all_clean_data.append(clean_item)
                                        current_batch += 1
                            
                            if current_batch > 0:
                                print(f"      + 抓取到 {current_batch} 条新评论 (累计: {len(all_clean_data)})")

            except Exception:
                pass
        
        # 随机等待
        time.sleep(random.uniform(1.5, 3))

    # --- 保存 ---
    print(f"\n💾 正在保存 {len(all_clean_data)} 条数据...")
    if not os.path.exists('data'): os.makedirs('data')
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_clean_data, f, ensure_ascii=False, indent=4)
    print(f"🎉 完成！文件在: {JSON_FILE}")

if __name__ == '__main__':
    spider_jd_blind_scroll()