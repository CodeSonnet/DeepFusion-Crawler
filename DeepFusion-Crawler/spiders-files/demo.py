import time
import json
import random
import os
from DrissionPage import ChromiumPage

# ================= 🛠️ 配置区域 =================
# 1. 商品链接
PRODUCT_URL = "https://item.jd.com/100209268189.html" # 换成你截图里那个链接了

# 2. 下滑次数
SCROLL_TIMES = 50 

# 3. 保存文件名
JSON_FILE = 'data/jd_popup_comments.json'
# ===============================================

def spider_jd_popup_fix():
    # 1. 启动
    dp = ChromiumPage()
    print("🚀 浏览器已启动...")

    # 2. 打开网页
    dp.get(PRODUCT_URL)
    time.sleep(2)

    # 3. 自动点击【全部评价】
    print("👀 寻找评价按钮...")
    # 先微微滚动背景，防止导航栏没出来
    dp.scroll.down(200)
    
    # 点击打开弹窗
    if dp.ele('text=全部评价'):
        dp.ele('text=全部评价').click()
    elif dp.ele('text=商品评价'):
        dp.ele('text=商品评价').click()
    else:
        input("❌ 没找到按钮，请手动点击【商品评价】/【全部评价】，然后按回车 >>")

    print("✅ 弹窗已打开，准备开始监听...")
    time.sleep(2)

    # 4. 开启监听 (监听所有京东域名的请求)
    dp.listen.start('jd.com') 
    
    all_clean_data = [] # 存放清洗后的数据

    # === 关键修正：定位弹窗 ===
    # 我们找弹窗里一定会有的文字，比如你截图里的 "全部 98%好评" 或者 "推荐排序"
    # 这里我们找 "全部" 这个标签，它肯定在弹窗最上面
    popup_anchor = dp.ele('text:98%好评') 
    
    if not popup_anchor:
        print("⚠️ 没自动找到弹窗锚点，请手动把鼠标移动到弹窗中间！")

    for i in range(SCROLL_TIMES):
        print(f"🔄 [第 {i+1} 次] 鼠标悬停并滚动...")
        
        # === 核心黑科技：鼠标操作 ===
        if popup_anchor:
            # 1. 把鼠标移到弹窗上的“好评”标签上 (确保鼠标在弹窗范围内)
            dp.actions.move_to(popup_anchor)
            # 2. 在当前位置向下滚动滚轮 (每次滚 500-800 像素)
            dp.actions.scroll(random.randint(500, 800))
        else:
            # 如果没找到锚点，就盲滚（假设你鼠标已经放好了）
            dp.scroll.down(500)
        
        # === 捕获数据 (解析逻辑完全对应你提供的 Floor 结构) ===
        res = dp.listen.wait(timeout=3)
        
        if res:
            try:
                raw_data = res.response.body
                
                # 检查是不是包含 floors 的那个包
                if isinstance(raw_data, dict) and 'result' in raw_data and 'floors' in raw_data['result']:
                    
                    floors = raw_data['result']['floors']
                    
                    # 遍历楼层，找评论列表
                    for floor in floors:
                        # 你之前的数据里，评论列表的 mId 是 'commentlist-list'
                        if floor.get('mId') == 'commentlist-list':
                            comment_list = floor.get('data', [])
                            
                            current_batch = 0
                            for item in comment_list:
                                # 提取 commentInfo
                                info = item.get('commentInfo', {})
                                
                                # 提取图片
                                pic_list = []
                                if 'pictureInfoList' in info:
                                    pic_list = [p.get('largePicURL', p.get('picURL')) for p in info['pictureInfoList']]

                                # 构造数据
                                clean_item = {
                                    "id": info.get('commentId'),
                                    "nickname": info.get('userNickName'),
                                    "score": info.get('commentScore'), 
                                    "content": info.get('commentData', '').replace('\n', ' '), # 对应 commentData
                                    "date": info.get('commentDate'), 
                                    "model": info.get('productSpecifications'), # 对应 productSpecifications
                                    "images": pic_list
                                }
                                
                                # 去重 (防止滚轮滚回去又抓一遍)
                                if clean_item not in all_clean_data:
                                    all_clean_data.append(clean_item)
                                    current_batch += 1
                            
                            if current_batch > 0:
                                print(f"   ✅ 抓取到 {current_batch} 条新评论 (累计: {len(all_clean_data)})")
                
            except Exception as e:
                pass
        
        # 随机等待
        time.sleep(random.uniform(2, 3))

    # 5. 保存
    print(f"\n💾 保存 {len(all_clean_data)} 条数据...")
    if not os.path.exists('data'): os.makedirs('data')
    
    with open(JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_clean_data, f, ensure_ascii=False, indent=4)
        
    print(f"🎉 完成！文件在: {JSON_FILE}")

if __name__ == '__main__':
    spider_jd_popup_fix()