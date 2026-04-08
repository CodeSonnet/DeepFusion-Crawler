import time
import json
import os
import random
import msvcrt
from DrissionPage import ChromiumPage, ChromiumOptions

# ================= ⚙️ 配置区域 =================
PRODUCT_NAME = "Redmi K90 pro max "  # 产品名称，用于标记数据来源
SHOP_URLS = [
    #oppo
    #没爬完"https://item.jd.com/100210407515.html?pcdk=OVilZt2LNvFZy5qoOjXdMm4sJOJR_mqNKygKlLC3Xl6d-Ks8qkds3s_dhoPblXSH.3z6a.aI3x&spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDQ2ODkuc2VhcmNoX2NvbmZpcm0lMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy4xJTIzc2t1X2NhcmQ",
    #"https://item.jd.com/10203573823021.html?pcdk=OVilZt2LNvFZy5qoOjXdMotZbMksMxmvV2pT5QYlweQHwtKCfgnwo13Yg_0GQ1fx.3z6a.aI3x&spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDQ2ODkuc2VhcmNoX2NvbmZpcm0lMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy4zJTIzc2t1X2NhcmQ",
    #"https://item.jd.com/100211467673.html?pcdk=OVilZt2LNvFZy5qoOjXdMm4sJOJR_mqNKygKlLC3Xl6-olGoJl3qJ8NDi-oEjBy3.3z6a.aI3x&spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDQ2ODkuc2VhcmNoX2NvbmZpcm0lMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy40JTIzc2t1X2NhcmQ",
    #"https://item.jd.com/10184249923683.html?pcdk=OVilZt2LNvFZy5qoOjXdMlpwWRYjrpDEswU-1eODn8MT_YyrlVuIoHWQQlErySCQ.3z6a.aI3x&spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDQ2ODkuc2VhcmNoX2NvbmZpcm0lMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy41JTIzc2t1X2NhcmQ",
   #红米
    "https://item.jd.com/100287758142.html?pcdk=V6-rBSwu8FP16K3G3Zhn1ITgSoAbYytl6He7e5JHCCzSP2Y1Qar-rFOiPzmXYaKX.3z6a.aI3x&spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDQ2ODkuc2VhcmNoX2NvbmZpcm0lMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy4xJTIzc2t1X2NhcmQ",
    "",
    "",
    "",
    "",
    "",
]

SCROLL_TIMES = 5000
JSON_FILE = 'data/JD/jd_Redmi_K90_pro_max.json'
USER_DATA_DIR = './JD_User_Data'  # 用户数据目录，保持登录态
# ===============================================


def check_captcha(dp):
    """检测京东人机验证弹窗"""
    captcha_signs = [
        'text:请完成验证', 'text:滑动验证', 'text:图形验证',
        'text:安全验证', 'text:人机验证',
        '#JDJRV-wrap',       # 京东验证码容器的常见ID
        '.JDJRV-bigimg',     # 京东滑块验证
    ]
    for sign in captcha_signs:
        try:
            if dp.ele(sign, timeout=0.5):
                return True
        except:
            pass
    return False


def human_scroll(dp):
    """模拟真实人类的浏览节奏，滚动幅度要足够大以触发新数据包加载"""
    action = random.choice(['space', 'scroll_medium', 'scroll_large'])

    if action == 'space':
        # 连按几次空格，一次空格翻不了多少
        for _ in range(random.randint(3, 6)):
            dp.actions.key_down('Space').key_up('Space')
            time.sleep(random.uniform(0.3, 0.8))
    elif action == 'scroll_medium':
        dp.scroll.down(random.randint(800, 1200))
    else:
        dp.scroll.down(random.randint(1200, 2000))

    # 模拟阅读时间 - 真人不会一直匀速滚动
    time.sleep(random.uniform(1.5, 4.0))


def save_incremental(all_data, json_file):
    """增量保存 - 每次抓到新数据立即写入，防止数据丢失"""
    os.makedirs(os.path.dirname(json_file), exist_ok=True)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=4)


def open_comment_popup(dp):
    """尝试打开评论弹窗，返回是否成功"""
    print("👀 尝试打开评论弹窗...")
    try:
        dp.scroll.down(500)
        time.sleep(random.uniform(2, 4))

        btn = dp.ele('text=全部评价') or dp.ele('text=商品评价')
        if btn:
            btn.click()
            print("✅ 弹窗已打开")
            return True
        else:
            input("❌ 自动打开失败，请手动点击后回车 >>")
            return True
    except:
        input("❌ 发生异常，请手动点击打开后回车 >>")
        return True


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

    # 【优化1】使用 User Data Dir 保持登录态
    co = ChromiumOptions()
    co.set_user_data_path(USER_DATA_DIR)
    dp = ChromiumPage(co)

    dp.listen.start('api.m.jd.com/client.action')
    is_paused = False

    print("\n" + "="*50)
    print("🎮 实时控制指南:")
    print("  [N] 键: 跳过当前商品, 爬下一个")
    print("  [P] 键: 暂停/继续切换")
    print("  [Ctrl+C]: 强制退出并保存")
    print("="*50 + "\n")

    try:
        for url in SHOP_URLS:
            if not url: continue
            print(f"\n🚀 启动任务: {url}")
            dp.get(url)
            time.sleep(5)

            # === 1. 打开弹窗 ===
            open_comment_popup(dp)
            print("💡 提示：运行过程中，随时按【Ctrl + C】可强制停止并保存数据！")
            time.sleep(5)

            # === 2. 循环抓取 ===
            no_data_rounds = 0
            try:
                for i in range(SCROLL_TIMES):
                    # --- 1. 实时交互控制 ---
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                        if key == 'n':
                            print("\n⏭️ 收到跳过指令，准备切换下一个商品...")
                            break
                        elif key == 'p':
                            is_paused = not is_paused
                            print(f"\n{'⏸️ 暂停' if is_paused else '▶️ 继续'} 程序运行...")

                    while is_paused:
                        if msvcrt.kbhit():
                            key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                            if key == 'p':
                                is_paused = False
                                print("\n▶️ 继续执行...")
                        time.sleep(0.5)

                    print(f"\r🔄 轮次: {i+1} | 总库: {len(all_data)} | 无响应轮数: {no_data_rounds} ", end="")

                    # 【优化3】人机验证检测 + 暂停等待
                    if check_captcha(dp):
                        print(f"\n⚠️ 检测到人机验证！正在紧急保存数据...")
                        save_incremental(all_data, JSON_FILE)
                        print(f"💾 数据已保存 ({len(all_data)} 条)")
                        input("🔐 请手动完成验证后，按回车继续 >>")
                        # 验证通过后重新打开评论弹窗
                        time.sleep(3)
                        open_comment_popup(dp)
                        time.sleep(5)
                        no_data_rounds = 0
                        continue

                    # 【优化4】拟人化滚动 — 幅度要大，确保翻过足够多评论触发新包
                    try:
                        last_item = dp.ele('.comment-item@@-1')
                        if last_item:
                            last_item.scroll.to_see()
                            time.sleep(random.uniform(0.3, 0.8))
                    except:
                        pass
                    human_scroll(dp)

                    # 等待数据加载
                    time.sleep(random.uniform(1.0, 2.0))

                    # --- 核心：队列清空模式 (Queue Draining) ---
                    packet_count = 0
                    for packet in dp.listen.steps(timeout=1):
                        try:
                            raw_json = packet.response.body
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

                    # --- 状态显示 + 【优化5】实时增量保存 ---
                    if packet_count > 0:
                        print(f"⚡ 爆发抓取! 处理了 {packet_count} 条新数据")
                        no_data_rounds = 0
                        # 每抓到数据就立即保存，再也不怕页面刷新/崩溃
                        save_incremental(all_data, JSON_FILE)
                    else:
                        print(f"中... {no_data_rounds}/10", end="")
                        no_data_rounds += 1

                    # 不自动停止，持续跑；仅在空轮次较多时给提示
                    if no_data_rounds == 20:
                        print(f"\n⚠️ 已连续 {no_data_rounds} 轮无新数据，仍在继续...（按 Ctrl+C 可手动停止）")
                    elif no_data_rounds > 0 and no_data_rounds % 50 == 0:
                        print(f"\n⚠️ 已连续 {no_data_rounds} 轮无新数据，考虑手动切换或 Ctrl+C 停止")

                    # === 【优化7】频率控制：在效率和安全之间取平衡 ===
                    if (i + 1) % random.randint(15, 25) == 0:
                        long_sleep = random.uniform(15, 30)
                        print(f"\n☕ 触发长休息机制，暂停 {long_sleep:.1f} 秒...")
                        time.sleep(long_sleep)
                    else:
                        short_sleep = random.uniform(3, 6)
                        time.sleep(short_sleep)

            except KeyboardInterrupt:
                print("\n🛑 用户强制停止！正在保存数据...")
                break
            except Exception as e:
                print(f"\n❌ 当前店铺发生错误: {e}，跳过并尝试保存...")
                save_incremental(all_data, JSON_FILE)
                continue

            # === 单个店铺爬完后保存 ===
            save_incremental(all_data, JSON_FILE)
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
        save_incremental(all_data, JSON_FILE)
        print(f"🎉 全部任务完成！总共保存 {len(all_data)} 条数据至: {JSON_FILE}")
    else:
        print("⚠️ 本次没有抓取到任何数据。")

if __name__ == '__main__':
    spider_jd_drain_mode()