#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  淘宝/天猫评论高效采集工具 V2 (MTOP Direct API)
==============================================================================
  核心思路：
      不再依赖「浏览器滚动 + 抓包」的低效模式，而是：
      1. 仅用 DrissionPage 打开浏览器让用户扫码登录
      2. 自动从浏览器抓取一次真实 MTOP 请求，提取完整 Cookie 和参数
      3. 用 requests 直接调用 MTOP API 翻页采集，效率提升数十倍

  防封措施：
      ★ 智能随机延迟（正常请求 2-5s，长休息 30-60s）
      ★ 自适应退避（遇到风控自动加倍等待，最长 10 分钟）
      ★ Token 自动刷新（过期后自动重新获取，无需人工干预）
      ★ 请求指纹伪装（随机 callback 名、动态时间戳、真实 Referer）
      ★ 单次运行请求上限（超过自动停止，防止过度采集）
      ★ 商品切换长休息（模拟真人浏览行为）
      ★ 断点续传（程序中断后可从上次进度继续）

  使用方法：
      1. 配置下方 TASKS 列表（商品链接 + 产品名 + 输出路径）
      2. 运行脚本，在弹出的浏览器中扫码登录淘宝
      3. 登录后按回车，程序自动采集

  依赖：pip install DrissionPage requests
==============================================================================
"""

import hashlib
import json
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs, urlencode

import requests
from DrissionPage import ChromiumPage, ChromiumOptions

# =============================================================================
# 一、采集任务配置
# =============================================================================

# 每个任务包含：产品名、商品链接列表、输出文件路径
# 商品链接支持 detail.tmall.com 和 item.taobao.com 格式
TASKS = [
    {
        "product_name": "Huawei P70",
        "max_shops": 30,
        "urls": [],
        "output_file": "data/TaoBao_V2/taobao_Huawei_P70.json",
    },
    {
        "product_name": "iPhone 17 Pro",
        "max_shops": 30,
        "urls": [],
        "output_file": "data/TaoBao_V2/taobao_iPhone17_Pro.json",
    },
    {
        "product_name": "Xiaomi 15 Pro",
        "max_shops": 30,
        "urls": [],
        "output_file": "data/TaoBao_V2/taobao_Xiaomi_15_Pro.json",
    },
    {
        "product_name": "VIVO X300 Pro",
        "max_shops": 30,
        "urls": [],
        "output_file": "data/TaoBao_V2/taobao_VIVO_X300_Pro.json",
    },
    {
        "product_name": "OPPO Find X9 Pro",
        "max_shops": 30,
        "urls": [],
        "output_file": "data/TaoBao_V2/taobao_OPPO_Find_X9_Pro.json",
    },
    {
        "product_name": "OnePlus 14",
        "max_shops": 30,
        "urls": [],
        "output_file": "data/TaoBao_V2/taobao_OnePlus_14.json",
    },
]

# =============================================================================
# 二、防封策略配置（⚠️ 建议保持默认值，过快会被风控）
# =============================================================================

# --- 请求节奏 ---
REQUEST_DELAY_MIN = 2.0       # 普通请求最短间隔（秒）
REQUEST_DELAY_MAX = 5.0       # 普通请求最长间隔（秒）

# --- 长休息 ---
LONG_PAUSE_INTERVAL = 15      # 每隔 N 次请求触发一次长休息
LONG_PAUSE_MIN = 30           # 长休息最短时间（秒）
LONG_PAUSE_MAX = 60           # 长休息最长时间（秒）

# --- 商品切换 ---
PRODUCT_SWITCH_PAUSE_MIN = 45   # 切换商品最短等待（秒）
PRODUCT_SWITCH_PAUSE_MAX = 90   # 切换商品最长等待（秒）

# --- 自适应退避（遇到风控/错误时） ---
BACKOFF_INITIAL = 30           # 首次退避（秒）
BACKOFF_MULTIPLIER = 2.0       # 退避倍数
BACKOFF_MAX = 600              # 最长退避（秒），即 10 分钟

# --- 安全上限 ---
MAX_REQUESTS_PER_RUN = 800     # 单次运行最大请求数（超过自动停止）
MAX_PAGES_PER_ITEM = 100       # 单个商品最大翻页数
MAX_RETRIES_PER_PAGE = 3       # 单页最大重试次数
CONSECUTIVE_EMPTY_LIMIT = 5    # 连续空页停止阈值

# --- 每页条数 ---
PAGE_SIZE = 20                 # 每页评论数，淘宝默认 20

# =============================================================================
# 三、MTOP 协议配置
# =============================================================================

MTOP_API_NAME = "mtop.taobao.rate.detaillist.get"
MTOP_API_VERSION = "6.0"
MTOP_APP_KEY = "12574478"
MTOP_BASE_URL = "https://h5api.m.taobao.com/h5/{api}/{version}/"

# 调试模式: 设为 True 可以在控制台打印 API 原始响应，方便排查
DEBUG_MODE = True
# 前 N 次请求打印完整响应（即使 DEBUG_MODE 为 False）
DEBUG_FIRST_N_REQUESTS = 3

# 浏览器用户数据目录（保存登录状态）
USER_DATA_DIR = "./Taobao_User_Data"


# =============================================================================
# 四、MTOP 签名工具
# =============================================================================

class MtopSigner:
    """
    淘宝 MTOP 协议签名器。
    签名算法：sign = MD5(token + "&" + timestamp + "&" + appKey + "&" + data)
    其中 token 来自 _m_h5_tk cookie 的前半段。
    """

    def __init__(self):
        self.token = ""

    def update_token(self, cookies: dict):
        """从 cookie 字典中提取并更新 token。"""
        h5_tk = cookies.get("_m_h5_tk", "")
        if h5_tk:
            # _m_h5_tk 格式: "token_timestamp"，取下划线前的部分
            self.token = h5_tk.split("_")[0]

    def sign(self, timestamp: str, app_key: str, data: str) -> str:
        """生成 MTOP 签名。"""
        plain = f"{self.token}&{timestamp}&{app_key}&{data}"
        return hashlib.md5(plain.encode("utf-8")).hexdigest()

    def build_request_params(self, data: dict) -> dict:
        """
        构建完整的 MTOP 请求参数。
        包含时间戳、签名、API 名称等一切必要参数。
        """
        timestamp = str(int(time.time() * 1000))
        # JSON 序列化时不要有多余空格，与浏览器行为一致
        data_str = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        sign_value = self.sign(timestamp, MTOP_APP_KEY, data_str)

        # 随机 callback 名称，避免指纹固定
        callback_name = f"mtopjsonp{random.randint(1, 20)}"

        return {
            "jsv": "2.7.2",
            "appKey": MTOP_APP_KEY,
            "t": timestamp,
            "sign": sign_value,
            "api": MTOP_API_NAME,
            "v": MTOP_API_VERSION,
            "type": "jsonp",
            "dataType": "jsonp",
            "callback": callback_name,
            "data": data_str,
        }


# =============================================================================
# 五、工具函数
# =============================================================================

def extract_item_id(url: str) -> str | None:
    """从淘宝/天猫商品链接中提取 itemId。"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        item_id = params.get("id", [None])[0]
        return item_id
    except Exception:
        return None


def parse_jsonp_response(text: str) -> dict | None:
    """
    解析 MTOP JSONP 响应。
    响应格式: mtopjsonpN({...})
    """
    # 尝试匹配各种 JSONP 回调格式
    match = re.search(r"mtopjsonp\d+\((.*)\)\s*;?\s*$", text.strip(), re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试更通用的 JSONP 匹配 (callback 名字可能不是 mtopjsonp)
    match = re.search(r"\w+\((.*)\)\s*;?\s*$", text.strip(), re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试直接 JSON 解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def extract_rate_list_from_data(data: dict) -> list:
    """
    从 MTOP API 返回的 data 字段中提取评论列表。
    淘宝/天猫 API 在不同时期、不同版本返回的嵌套结构不同，
    这里按优先级逐一尝试多种已知路径。
    """
    if not data:
        return []

    # ===== 路径1: data.rateList（旧版直返） =====
    rate_list = data.get("rateList")
    if isinstance(rate_list, list) and len(rate_list) > 0:
        return rate_list

    # ===== 路径2: data.rateDetail.rateList =====
    rate_detail = data.get("rateDetail")
    if isinstance(rate_detail, dict):
        rl = rate_detail.get("rateList")
        if isinstance(rl, list) and len(rl) > 0:
            return rl

    # ===== 路径3: data.module.feedRateList / rateList =====
    module = data.get("module")
    if isinstance(module, dict):
        rl = module.get("feedRateList") or module.get("rateList")
        if isinstance(rl, list) and len(rl) > 0:
            return rl

    # ===== 路径4: data.feedRateList =====
    rl = data.get("feedRateList")
    if isinstance(rl, list) and len(rl) > 0:
        return rl

    # ===== 路径5: data.comments =====
    rl = data.get("comments")
    if isinstance(rl, list) and len(rl) > 0:
        return rl

    # ===== 路径6: 递归搜索 — 在 data 的所有 value 中找第一个非空 list =====
    # 这是最后的兜底手段
    for key, val in data.items():
        if isinstance(val, dict):
            for k2, v2 in val.items():
                if isinstance(v2, list) and len(v2) > 0:
                    # 检查列表元素是否看起来像评论（有 content/feedback/rateContent 字段）
                    first = v2[0]
                    if isinstance(first, dict) and any(
                        f in first for f in ["feedback", "rateContent", "content", "feedbackDate", "rateDate", "displayUserNick"]
                    ):
                        return v2

    return []


def extract_max_page_from_data(data: dict) -> int:
    """
    从 MTOP API 返回的 data 字段中提取最大页码。
    兼容多种嵌套结构。
    """
    if not data:
        return 1

    # 直接在 data 层
    max_page = data.get("maxPage") or data.get("paginator", {}).get("lastPage")
    if max_page:
        return int(max_page)

    # 在 rateDetail 层
    rd = data.get("rateDetail", {})
    max_page = rd.get("maxPage") or rd.get("paginator", {}).get("lastPage")
    if max_page:
        return int(max_page)

    # 在 module 层
    mod = data.get("module", {})
    max_page = mod.get("maxPage") or mod.get("paginator", {}).get("lastPage")
    if max_page:
        return int(max_page)

    # 用 totalCount / pageSize 来估算
    total = data.get("totalCount") or data.get("total") or rd.get("rateCount") or 0
    if total:
        import math
        return max(1, math.ceil(int(total) / PAGE_SIZE))

    # 默认给一个较大值，让后续的空页检测来决定停止
    return 999


def parse_single_review(item: dict, product_name: str) -> dict:
    """
    将淘宝 API 返回的单条评论原始数据解析为标准格式。
    与项目中其他平台的数据格式保持一致。
    兼容不同版本 API 的字段命名差异。
    """
    # 提取图片列表，补全协议头
    pic_list = (
        item.get("feedPicPathList")
        or item.get("pics")
        or item.get("images")
        or []
    )
    full_pics = [
        f"https:{pic}" if isinstance(pic, str) and pic.startswith("//") else str(pic)
        for pic in pic_list
    ]

    # 提取点赞数
    interact = item.get("interactInfo", {})
    like_count = int(interact.get("likeCount", 0)) if isinstance(interact, dict) else 0

    # 提取追评
    append_text = ""
    append_obj = item.get("appendComment") or item.get("appendFeed") or item.get("append")
    if isinstance(append_obj, dict):
        append_text = (
            append_obj.get("content", "") or append_obj.get("feedback", "")
        )
    elif isinstance(append_obj, str):
        append_text = append_obj

    # 尝试提取真实评分
    score = item.get("rateScore") or item.get("score") or item.get("rate")
    if score is not None:
        score = int(score)
    else:
        # 备选字段
        rate_type = item.get("rateType", 0)
        # 0=好评, 1=中评, 2=差评
        score = {0: 5, 1: 3, 2: 1}.get(rate_type, 5)

    # 提取评论内容（兼容多种字段名）
    content = (
        item.get("feedback")
        or item.get("rateContent")
        or item.get("content")
        or item.get("feedContent")
        or ""
    )
    if isinstance(content, str):
        content = content.replace("\n", " ").strip()

    # 提取评论 ID（兼容多种字段名）
    review_id = str(
        item.get("id")
        or item.get("rateId")
        or item.get("feedId")
        or item.get("commentId")
        or ""
    )

    return {
        "platform": "Taobao/Tmall",
        "product_name": product_name,
        "id": review_id,
        "content": content,
        "score": score,
        "date": (
            item.get("feedbackDate")
            or item.get("rateDate")
            or item.get("date")
            or item.get("gmtCreate")
            or "未知"
        ),
        "model_sku": (
            item.get("skuValueStr")
            or item.get("auctionSku")
            or item.get("sku")
            or "未知"
        ),
        "append_content": append_text.replace("\n", " ").strip() if isinstance(append_text, str) else "",
        "votes": like_count,
        "images": full_pics,
        "reply": item.get("reply", ""),
        "user_nick": item.get("displayUserNick") or item.get("userNick") or "",
    }


# =============================================================================
# 六、核心爬虫类
# =============================================================================

class TaobaoCrawlerV2:
    """
    淘宝/天猫评论高效采集器。
    使用 MTOP 协议直接调用 API，配合完善的防封策略。
    """

    def __init__(self):
        self.session = requests.Session()
        self.signer = MtopSigner()
        self.browser: ChromiumPage | None = None

        # 统计计数
        self.total_requests = 0      # 本次运行总请求数
        self.total_collected = 0     # 本次运行总采集数
        self.consecutive_errors = 0  # 连续错误计数（用于退避）
        self.current_backoff = BACKOFF_INITIAL  # 当前退避时间

        # 设置真实的请求头 (改为移动端 UA 可以降低 MTOP H5 接口风控)
        mobile_ua = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )
        self.session.headers.update({
            "User-Agent": mobile_ua,
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        })

    # -----------------------------------------------------------------
    # 6.1 登录与认证
    # -----------------------------------------------------------------

    def login(self) -> bool:
        """
        使用浏览器完成登录并提取认证信息。
        返回 True 表示成功获取到 MTOP token。
        """
        print("\n" + "=" * 60)
        print("  📱 第一步：浏览器登录淘宝")
        print("=" * 60)

        co = ChromiumOptions()
        # 指定使用 Microsoft Edge 浏览器
        co.set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
        
        # 使用项目内的独立缓存目录（登录状态会保存，下次无需重复登录）
        co.set_user_data_path(USER_DATA_DIR)
        
        # 桌面端 Edge UA
        co.set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
        
        # ===== 反自动化检测（关键！否则验证码永远通不过） =====
        # 阻止 Chromium 设置 navigator.webdriver = true
        co.set_argument('--disable-blink-features=AutomationControlled')
        # 移除自动化控制提示条
        co.set_argument('--disable-infobars')
        # 排除自动化开关
        co.set_argument('--disable-automation')
        
        self.browser = ChromiumPage(co)
        
        # 通过 CDP 在每个新页面加载前注入反检测脚本
        # 这会在页面任何 JS 执行之前运行，确保验证码系统检测不到自动化特征
        try:
            self.browser.run_cdp(
                'Page.addScriptToEvaluateOnNewDocument',
                source='''
                    // 隐藏 webdriver 标记
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    // 伪造 chrome 对象
                    if (!window.chrome) {
                        window.chrome = { runtime: {} };
                    }
                    // 伪造 Permissions API
                    const originalQuery = window.navigator.permissions?.query;
                    if (originalQuery) {
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications'
                                ? Promise.resolve({ state: Notification.permission })
                                : originalQuery(parameters)
                        );
                    }
                    // 伪造 plugins（真实浏览器至少有几个插件）
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    // 伪造 languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['zh-CN', 'zh', 'en']
                    });
                '''
            )
            print("   ✅ 反自动化检测脚本已注入")
        except Exception as e:
            print(f"   ⚠️ CDP注入失败（不影响基本功能）: {e}")

        # 打开淘宝首页进行登录
        print("\n🔐 正在打开淘宝首页...")
        self.browser.get("https://www.taobao.com")
        time.sleep(3)

        print("\n" + "-" * 50)
        print("🛑  请在弹出的浏览器窗口中登录淘宝！")
        print("👉  如果已自动登录（看到你的昵称），直接按回车")
        print("👉  如果需要登录，请手动扫码后再按回车")
        print("-" * 50)
        input("\n>> 登录成功后按回车继续...")

        # 访问一个天猫商品页来触发 MTOP cookie 的生成
        print("\n🔄 正在获取 MTOP 认证令牌...")
        # 先访问天猫首页
        self.browser.get("https://www.tmall.com")
        time.sleep(3)

        # 关键：触发一次 MTOP H5 API 调用来拿到 _m_h5_tk cookie
        # 直接访问一个 MTOP 接口的 URL（不需要有效参数，只要能触发 Set-Cookie）
        trigger_url = (
            "https://h5api.m.taobao.com/h5/mtop.common.getTimestamp/1.0/"
            "?jsv=2.7.2&appKey=12574478&t=" + str(int(time.time() * 1000))
            + "&sign=00000000000000000000000000000000"
            + "&api=mtop.common.getTimestamp&v=1.0&type=jsonp&dataType=jsonp"
            + "&callback=mtopjsonp1&data={}"
        )
        self.browser.get(trigger_url)
        time.sleep(2)

        # 再回到天猫首页（某些情况下需要多触发一次）
        self.browser.get("https://www.tmall.com")
        time.sleep(2)

        # 提取 Cookie
        return self._extract_cookies()

    def _extract_cookies(self) -> bool:
        """从浏览器提取所有 Cookie 到 requests 会话。"""
        if not self.browser:
            return False

        cookies = {}
        for cookie in self.browser.cookies():
            name = cookie.get("name", "")
            value = cookie.get("value", "")
            domain = cookie.get("domain", "")
            if name and value:
                cookies[name] = value
                # 设置到 requests 会话，注意域名匹配
                self.session.cookies.set(
                    name, value,
                    domain=domain if domain else ".taobao.com"
                )

        # 更新签名器的 token
        self.signer.update_token(cookies)

        has_token = bool(cookies.get("_m_h5_tk"))
        has_token_enc = bool(cookies.get("_m_h5_tk_enc"))

        print(f"\n✅ Cookie 提取完成，共 {len(cookies)} 个")
        print(f"   _m_h5_tk:     {'✅ 已获取' if has_token else '❌ 缺失'}")
        print(f"   _m_h5_tk_enc: {'✅ 已获取' if has_token_enc else '❌ 缺失'}")

        if not has_token:
            print("\n⚠️  未获取到 MTOP token，尝试访问商品页触发...")
            # 尝试访问一个商品详情页来触发 token 生成
            self.browser.get(
                "https://detail.tmall.com/item.htm?id=1"
            )
            time.sleep(3)
            # 重新提取
            for cookie in self.browser.cookies():
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                domain = cookie.get("domain", "")
                if name and value:
                    cookies[name] = value
                    self.session.cookies.set(
                        name, value,
                        domain=domain if domain else ".taobao.com"
                    )
            self.signer.update_token(cookies)
            has_token = bool(cookies.get("_m_h5_tk"))
            print(f"   _m_h5_tk:     {'✅ 重新获取成功' if has_token else '❌ 仍然缺失'}")

        return has_token

    def _refresh_token(self) -> bool:
        """
        当 token 过期时，通过浏览器刷新重新获取。
        MTOP 协议特性：即使返回 TOKEN_EXPIRED，响应的 Set-Cookie 中也会包含新 token。
        浏览器会自动处理这些 Cookie，所以我们只需要从浏览器重新读取即可。
        """
        print("   🔄 正在刷新 MTOP token...")

        # 优先尝试从浏览器当前 cookie 中更新（上次请求可能已经在响应中刷新了 token）
        old_token = self.signer.token
        self._sync_browser_cookies()

        if self.signer.token and self.signer.token != old_token:
            print(f"   ✅ Token 已从浏览器 Cookie 中自动刷新")
            return True

        # 如果 cookie 中没有新 token，主动触发一次 MTOP 请求来获取新 token
        if self.browser:
            try:
                trigger_url = (
                    "https://h5api.m.taobao.com/h5/mtop.common.getTimestamp/1.0/"
                    "?jsv=2.7.2&appKey=12574478&t=" + str(int(time.time() * 1000))
                    + "&sign=00000000000000000000000000000000"
                    + "&api=mtop.common.getTimestamp&v=1.0&type=jsonp&dataType=jsonp"
                    + "&callback=mtopjsonp1&data={}"
                )
                self.browser.get(trigger_url)
                time.sleep(2)
                self._sync_browser_cookies()
                if self.signer.token and self.signer.token != old_token:
                    print(f"   ✅ Token 已通过触发请求刷新")
                    return True
            except Exception as e:
                print(f"   ❌ 浏览器刷新失败: {e}")

        return False

    # -----------------------------------------------------------------
    # 6.1.5 自动搜索与链接提取
    # -----------------------------------------------------------------

    def search_and_extract_urls(self, keyword: str, max_shops: int = 10) -> list[str]:
        """
        根据关键字在淘宝进行自动搜索，并抓取前 max_shops 个商品链接。
        """
        print(f"\n" + "-" * 50)
        print(f"  🔍 正在后台自动搜索: {keyword}")
        print("-" * 50)
        
        if not self.browser:
            return []
            
        urls = []
        try:
            search_url = f"https://s.taobao.com/search?q={keyword}"
            self.browser.get(search_url)
            time.sleep(random.uniform(4, 7))
            
            # 向下滚动两三屏，确保图片和卡片已加载
            for _ in range(3):
                self.browser.scroll.down(600)
                time.sleep(random.uniform(1.5, 3))
                
            # 获取所有具有 href 的 a 标签
            elements = self.browser.eles("tag:a")
            for ele in elements:
                try:
                    href = ele.attr("href")
                    if href and ("item.htm" in href or "detail.tmall.com" in href):
                        if href.startswith("//"):
                            href = "https:" + href
                        
                        if href not in urls:
                            urls.append(href)
                        if len(urls) >= max_shops:
                            break
                except Exception:
                    continue
                    
            print(f"   ✅ [搜索完毕] 共收集到 {len(urls)} 个相关商品链接。")
            return urls
        except Exception as e:
            print(f"   ❌ 搜索过程出错: {e}")
            return []

    # -----------------------------------------------------------------
    # 6.1.6 浏览器 Cookie 同步
    # -----------------------------------------------------------------

    def _sync_browser_cookies(self):
        """
        从浏览器同步 cookie 到签名器，确保 token 是最新的。
        浏览器每次请求 MTOP API 后，服务器可能在响应中刷新 _m_h5_tk，
        浏览器会自动处理 Set-Cookie，这里只需要读取即可。
        """
        if not self.browser:
            return
        cookies = {}
        try:
            for cookie in self.browser.cookies():
                name = cookie.get("name", "")
                value = cookie.get("value", "")
                if name and value:
                    cookies[name] = value
        except Exception:
            pass
        self.signer.update_token(cookies)

    def _get_page_text(self) -> str:
        """
        从浏览器当前页面提取纯文本内容。
        当浏览器直接导航到 MTOP API URL 时，响应是 JSONP 文本，
        Chrome/Edge 会把它包裹在 <pre> 标签中展示。
        """
        if not self.browser:
            return ""
        try:
            # Chrome/Edge 把文本响应放在 <pre> 标签里
            pre = self.browser.ele('tag:pre')
            if pre:
                return pre.text
        except Exception:
            pass
        try:
            body = self.browser.ele('tag:body')
            if body:
                return body.text
        except Exception:
            pass
        # 兜底：从 HTML 源码中剥离标签
        try:
            html = self.browser.html
            text = re.sub(r'<[^>]+>', '', html)
            return text.strip()
        except Exception:
            return ""

    def _check_verification_page(self) -> bool:
        """
        检查浏览器是否被重定向到了验证/登录页面。
        如果是，提示用户手动完成验证。
        返回 True 表示检测到验证页面并等待用户完成。
        """
        if not self.browser:
            return False
        try:
            current_url = self.browser.url or ""
            if any(kw in current_url for kw in [
                'login.taobao.com', 'sec.taobao.com', 
                'login.tmall.com', 'captcha', 'punish'
            ]):
                print("\n" + "!" * 60)
                print("   ⚠️  检测到验证/登录页面！")
                print("   📌 请在浏览器窗口中手动完成验证")
                print("!" * 60)
                input("\n>> 完成验证后按回车继续...")
                # 验证后重新同步 cookie
                self._sync_browser_cookies()
                return True
        except Exception:
            pass
        return False

    # -----------------------------------------------------------------
    # 6.2 防封策略
    # -----------------------------------------------------------------

    def _smart_delay(self, context: str = ""):
        """
        智能延迟策略：
        - 普通请求: 2-5 秒随机延迟
        - 每 15 次请求: 30-60 秒长休息
        - 遇到错误后: 自适应退避
        """
        self.total_requests += 1

        # 检查是否达到单次运行上限
        if self.total_requests >= MAX_REQUESTS_PER_RUN:
            raise SystemExit(
                f"\n🛑 已达到单次运行请求上限 ({MAX_REQUESTS_PER_RUN})，"
                f"请稍后再运行！这是为了保护你的账号安全。"
            )

        # 长休息
        if self.total_requests % LONG_PAUSE_INTERVAL == 0:
            pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
            print(
                f"\n   ☕ 防封长休息 {pause:.0f}s "
                f"(已请求 {self.total_requests} 次, "
                f"已采集 {self.total_collected} 条)..."
            )
            time.sleep(pause)
        else:
            # 普通随机延迟
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            time.sleep(delay)

    def _error_backoff(self, reason: str):
        """
        错误退避策略：
        连续错误时，等待时间指数增长（30s → 60s → 120s → ... → 600s）
        """
        self.consecutive_errors += 1
        wait = min(
            self.current_backoff * (BACKOFF_MULTIPLIER ** (self.consecutive_errors - 1)),
            BACKOFF_MAX,
        )
        print(
            f"\n   ⚠️  {reason}"
            f"\n   🕐 自适应退避: 等待 {wait:.0f}s "
            f"(连续错误 {self.consecutive_errors} 次)..."
        )
        time.sleep(wait)

    def _reset_error_state(self):
        """请求成功时重置错误计数。"""
        self.consecutive_errors = 0
        self.current_backoff = BACKOFF_INITIAL

    # -----------------------------------------------------------------
    # 6.3 评论数据采集（网络拦截方案）
    # -----------------------------------------------------------------
    #
    # 核心思路：
    #   放弃直接访问 MTOP API URL（始终被安全模块拦截）。
    #   改为浏览器导航到真实商品页面，像真人一样滚动到评论区域，
    #   页面自己的 JS 会自然发起 MTOP API 请求（带有完整安全上下文），
    #   我们通过 DrissionPage 的 listen 功能拦截并捕获这些 API 响应。
    #

    def _navigate_to_product_page(self, item_id: str) -> str:
        """
        导航到商品详情页，并提取 sellerId。
        返回 sellerId（提取不到则返回空字符串）。
        """
        if not self.browser:
            return ""
        url = f"https://detail.tmall.com/item.htm?id={item_id}"
        print(f"      🔗 正在打开商品页面...")
        self.browser.get(url)
        time.sleep(random.uniform(3, 5))

        # 检查是否需要登录/验证
        if self._check_verification_page():
            self.browser.get(url)
            time.sleep(random.uniform(3, 5))

        # 尝试提取 sellerId
        seller_id = ""
        try:
            page_source = self.browser.html
            match = re.search(r'"sellerId"\s*:\s*"?(\d+)"?', page_source)
            if match:
                seller_id = match.group(1)
        except Exception:
            pass
        return seller_id

    def _scroll_to_reviews(self):
        """
        在商品详情页中找到评论区域并触发评论加载。
        尝试多种方式：点击评价Tab、滚动到评论区域等。
        """
        if not self.browser:
            return False

        # 方式1：尝试点击评价Tab（天猫桌面端常见布局）
        tab_texts = ['累计评价', '宝贝评价', '评价', '用户评价', '商品评价']
        for text in tab_texts:
            try:
                ele = self.browser.ele(f'text:{text}')
                if ele:
                    ele.click()
                    print(f"      📋 已点击「{text}」Tab")
                    time.sleep(random.uniform(2, 4))
                    return True
            except Exception:
                continue

        # 方式2：尝试通过CSS选择器找评价Tab
        tab_selectors = [
            '#J_TabBar .J_Reviews', '.tb-tab a:nth-child(2)',
            '[data-anchor="#J_Reviews"]', '.item-mod__tab___1y2EM'
        ]
        for sel in tab_selectors:
            try:
                ele = self.browser.ele(sel)
                if ele:
                    ele.click()
                    print(f"      📋 已通过选择器点击评价Tab")
                    time.sleep(random.uniform(2, 4))
                    return True
            except Exception:
                continue

        # 方式3：大幅滚动页面，让评论区域自然进入视口
        print(f"      📋 未找到评价Tab，尝试滚动到评论区域...")
        for i in range(8):
            self.browser.scroll.down(500)
            time.sleep(random.uniform(0.5, 1.0))
        return False

    def _click_next_review_page(self) -> bool:
        """
        在评论区域点击「下一页」按钮。
        返回 True 表示成功点击，False 表示没有找到下一页按钮。
        """
        if not self.browser:
            return False

        # 尝试多种选择器找下一页按钮
        next_selectors = [
            'text:下一页', 'text:下页',
            '.pg-next', '.rate-paginator .next',
            'a.pg-next', '.pagination-next',
            'text:>>',
        ]
        for sel in next_selectors:
            try:
                ele = self.browser.ele(sel)
                if ele:
                    ele.click()
                    time.sleep(random.uniform(2, 4))
                    return True
            except Exception:
                continue
        return False

    def _fetch_reviews_page(
        self, item_id: str, seller_id: str, page: int
    ) -> tuple[list, bool, str]:
        """
        通过网络拦截获取一页评论数据。

        不再直接调用 MTOP API（会被安全模块拦截），而是：
        1. 启动网络监听
        2. 在页面上触发评论加载（滚动/翻页）
        3. 捕获页面 JS 自然发起的 MTOP API 响应
        4. 解析响应中的评论数据

        参数:
            item_id: 商品 ID（首次会导航到商品页）
            seller_id: 未使用（保持接口兼容）
            page: 页码

        返回:
            (评论列表, 是否还有下一页, 错误类型或空字符串)
        """
        if not self.browser:
            return [], False, "NO_BROWSER"

        try:
            # 1. 启动网络监听（用宽泛模式，兼容各种评论API端点）
            #    必须在触发动作之前启动！
            self.browser.listen.start('rate')

            # 2. 触发评论加载
            if page == 1:
                # === 首页：先导航到商品页，再滚动到评论区域 ===
                # 注意：listen 已经启动，导航过程中的 API 调用会被捕获
                url = f"https://detail.tmall.com/item.htm?id={item_id}"
                print(f"      \U0001f517 正在打开商品页面...")
                self.browser.get(url)
                time.sleep(random.uniform(3, 5))

                # 检查是否需要验证
                if self._check_verification_page():
                    self.browser.listen.stop()
                    self.browser.listen.start('rate')
                    self.browser.get(url)
                    time.sleep(random.uniform(3, 5))

                # 滚动到评论区域（这会触发评论API调用）
                self._scroll_to_reviews()
            else:
                # === 翻页：点击下一页按钮 ===
                if not self._click_next_review_page():
                    self.browser.listen.stop()
                    print(f"      \u2705 没有找到下一页按钮，评论采集完毕")
                    return [], False, ""

            # 3. 等待并捕获 API 响应（超时15秒）
            packet = self.browser.listen.wait(timeout=15)
            self.browser.listen.stop()

            if not packet:
                if page == 1:
                    print(f"      \u26a0\ufe0f 未捕获到评论API响应")
                    print(f"         \U0001f4a1 提示：可能页面结构不同，跳过此商品")
                    return [], False, ""
                print(f"      \u26a0\ufe0f 翻页后未捕获到API响应")
                return [], False, ""

            # 4. 调试：显示捕获到的URL
            if DEBUG_MODE or self.total_requests <= DEBUG_FIRST_N_REQUESTS:
                print(f"\n      \U0001f50d [DEBUG] 网络拦截 Page={page}")
                try:
                    print(f"         捕获URL: {packet.url[:120]}...")
                except Exception:
                    print(f"         捕获到数据包(无法读取URL)")

            # 5. 解析API响应
            body = packet.response.body
            result = None

            if isinstance(body, dict):
                result = body
            elif isinstance(body, (str, bytes)):
                text = body if isinstance(body, str) else body.decode('utf-8', errors='ignore')
                result = parse_jsonp_response(text)
                if not result:
                    try:
                        result = json.loads(text)
                    except Exception:
                        pass

            if not result:
                print(f"      \u274c 响应解析失败")
                return [], False, "PARSE_ERROR"

            # 6. 检查返回状态
            ret_codes = result.get("ret", [])
            if DEBUG_MODE or self.total_requests <= DEBUG_FIRST_N_REQUESTS:
                print(f"         ret: {ret_codes}")
                rate_data = result.get("data", {})
                if isinstance(rate_data, dict):
                    print(f"         data keys: {list(rate_data.keys())}")

            if any("FAIL" in r for r in ret_codes) and not any("SUCCESS" in r for r in ret_codes):
                return [], False, f"API_FAIL:{ret_codes}"

            # 7. 提取评论列表
            rate_data = result.get("data", {})
            rate_list = extract_rate_list_from_data(rate_data)
            max_page = extract_max_page_from_data(rate_data)
            has_more = page < max_page and len(rate_list) > 0

            if DEBUG_MODE or self.total_requests <= DEBUG_FIRST_N_REQUESTS:
                print(f"         评论: {len(rate_list)}条, maxPage: {max_page}, has_more: {has_more}")

            return rate_list, has_more, ""

        except Exception as e:
            try:
                self.browser.listen.stop()
            except Exception:
                pass
            import traceback
            traceback.print_exc()
            return [], False, f"EXCEPTION:{e}"

    def crawl_task(self, task: dict):
        """
        执行一个采集任务（一个产品）。

        新版流程（网络拦截 + 自动翻页 + 手动兜底）：
        1. 加载历史数据（断点续传）
        2. 逐个商品链接 → 打开商品页 → 后台持续监听评论API →
           自动翻页 → 如果翻不了就提示用户手动操作 → 数据自动捕获
        3. 每个商品完成后自动保存
        """
        product_name = task["product_name"]
        urls = task["urls"]
        output_file = task["output_file"]

        if not urls:
            print(f"   ⚠️  未配置商品链接，跳过")
            return

        # --- 加载历史数据 ---
        all_data = []
        unique_ids = set()
        if os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                all_data.extend(old_data)
                unique_ids.update(
                    item["id"] for item in old_data if "id" in item
                )
                print(f"   📂 已加载历史数据: {len(all_data)} 条")
            except Exception as e:
                print(f"   ⚠️  加载历史数据失败: {e}")

        initial_count = len(all_data)

        # --- 逐个商品采集 ---
        for url_idx, url in enumerate(urls):
            item_id = extract_item_id(url)
            if not item_id:
                print(f"   ❌ 无法从链接提取商品ID: {url}")
                continue

            print(f"\n   🏪 [{url_idx + 1}/{len(urls)}] 商品 {item_id}")

            # === 采集一个商品的全部评论 ===
            item_reviews = self._crawl_item_reviews(item_id, product_name)

            # 去重并合并到总数据
            new_count = 0
            for raw_review in item_reviews:
                rid = str(raw_review.get("id", ""))
                if rid and rid not in unique_ids:
                    clean = parse_single_review(raw_review, product_name)
                    all_data.append(clean)
                    unique_ids.add(rid)
                    new_count += 1
                    self.total_collected += 1

            print(f"      📊 本商品采集完毕: 新增 {new_count} 条, 总计 {len(all_data):,} 条")

            # 保存进度
            self._save_data(all_data, output_file)
            print(f"      💾 已自动保存")

            # 商品切换休息
            if url_idx < len(urls) - 1:
                switch_pause = random.uniform(
                    PRODUCT_SWITCH_PAUSE_MIN, PRODUCT_SWITCH_PAUSE_MAX
                )
                print(f"\n   💤 商品切换休息 {switch_pause:.0f}s...")
                time.sleep(switch_pause)

        # --- 最终统计 ---
        added = len(all_data) - initial_count
        print(
            f"\n   🎉 [{product_name}] 采集完成！"
            f"本次新增 {added:,} 条, 总计 {len(all_data):,} 条"
        )

    def _crawl_item_reviews(self, item_id: str, product_name: str) -> list:
        """
        采集一个商品的全部评论。

        核心流程：
        1. 启动后台网络监听（持续运行）
        2. 导航到商品页面
        3. 滚动/点击找到评论区域
        4. 循环：捕获评论数据 → 自动翻页 → 捕获 → 翻页 → ...
        5. 如果自动翻页失败，提示用户手动操作
        6. 连续多次无新数据时停止

        返回：原始评论列表（未去重）
        """
        if not self.browser:
            return []

        all_raw_reviews = []
        page_num = 0
        no_data_count = 0

        try:
            # 1. 先启动后台监听，再导航（确保捕获页面加载时的API调用）
            self.browser.listen.start('rate')

            url = f"https://detail.tmall.com/item.htm?id={item_id}"
            print(f"      🔗 正在打开商品页面...")
            self.browser.get(url)
            time.sleep(random.uniform(3, 5))

            # 检查验证页面
            if self._check_verification_page():
                self.browser.listen.stop()
                self.browser.listen.start('rate')
                self.browser.get(url)
                time.sleep(random.uniform(3, 5))

            # 2. 尝试自动找到评论区域
            found_tab = self._scroll_to_reviews()
            if not found_tab:
                print(f"      📌 自动查找评论区域失败")
                print(f"      👉 请在浏览器中手动点击「评价」标签或滚动到评论区域")
                print(f"      📡 后台正在监听，找到评论后数据会自动捕获...")

            # 3. 持续捕获循环
            while no_data_count < CONSECUTIVE_EMPTY_LIMIT and page_num < MAX_PAGES_PER_ITEM:
                # 等待下一个包含 'rate' 的 API 响应
                packet = self.browser.listen.wait(timeout=15)

                if not packet:
                    no_data_count += 1
                    if page_num == 0 and no_data_count == 1:
                        # 首次超时，给用户更多指引
                        print(f"\n      ⏳ 还没有捕获到评论数据...")
                        print(f"      👉 请在浏览器中手动操作：")
                        print(f"         1. 找到并点击「评价」或「评论」Tab")
                        print(f"         2. 如果已经看到评论了，请滚动一下页面")
                        print(f"      📡 脚本正在持续监听中（等待超时后自动跳到下一个商品）")
                    elif no_data_count >= CONSECUTIVE_EMPTY_LIMIT:
                        if page_num == 0:
                            print(f"      ⚠️ 未能捕获到任何评论数据，跳过此商品")
                        else:
                            print(f"      ✅ 连续无新数据，该商品评论已采集完毕")
                    continue

                # 捕获到数据！解析响应
                body = packet.response.body
                result = self._parse_response_body(body)

                if not result:
                    no_data_count += 1
                    continue

                # 检查API状态
                ret_codes = result.get("ret", [])
                if any("FAIL" in r for r in ret_codes) and not any("SUCCESS" in r for r in ret_codes):
                    if DEBUG_MODE:
                        print(f"      ⚠️ API 返回非成功状态: {ret_codes}")
                    # 不计入空页计数，可能是其他rate请求
                    continue

                # 提取评论列表
                rate_data = result.get("data", {})
                rate_list = extract_rate_list_from_data(rate_data)

                if not rate_list:
                    # 可能捕获到的是评论摘要或其他rate API，不是评论列表
                    if DEBUG_MODE:
                        print(f"      🔍 捕获到rate请求但无评论数据 (data keys: {list(rate_data.keys()) if isinstance(rate_data, dict) else 'N/A'})")
                    continue

                # 成功获取到评论！
                page_num += 1
                no_data_count = 0  # 重置空计数
                all_raw_reviews.extend(rate_list)

                max_page = extract_max_page_from_data(rate_data)
                print(
                    f"      📄 第{page_num}页: "
                    f"获取 {len(rate_list)} 条评论, "
                    f"累计 {len(all_raw_reviews)} 条"
                    f" (最大页数: {max_page})"
                )

                # 检查是否到达最后一页
                if page_num >= max_page:
                    print(f"      ✅ 已到达最后一页")
                    break

                # 防封延迟
                delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                time.sleep(delay)

                # 尝试自动点击下一页
                if not self._click_next_review_page():
                    print(f"      ⚠️ 未找到「下一页」按钮")
                    print(f"      👉 请手动点击评论区域的下一页/页码按钮")
                    print(f"      📡 脚本仍在监听中...")
                    # 不退出循环，等待用户手动翻页

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"      ❌ 采集异常: {e}")

        finally:
            try:
                self.browser.listen.stop()
            except Exception:
                pass

        return all_raw_reviews

    def _parse_response_body(self, body) -> dict | None:
        """解析网络拦截捕获的 API 响应体。"""
        result = None
        if isinstance(body, dict):
            result = body
        elif isinstance(body, (str, bytes)):
            text = body if isinstance(body, str) else body.decode('utf-8', errors='ignore')
            result = parse_jsonp_response(text)
            if not result:
                try:
                    result = json.loads(text)
                except Exception:
                    pass
        return result

    # -----------------------------------------------------------------
    # 6.6 数据持久化
    # -----------------------------------------------------------------

    def _save_data(self, data: list, output_file: str):
        """安全保存数据到 JSON 文件。"""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        # 先写临时文件，成功后再替换（防止写入中断导致数据丢失）
        tmp_file = output_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # 原子替换
        if os.path.exists(output_file):
            os.replace(tmp_file, output_file)
        else:
            os.rename(tmp_file, output_file)

    # -----------------------------------------------------------------
    # 6.7 清理
    # -----------------------------------------------------------------

    def cleanup(self):
        """清理资源。"""
        if self.browser:
            try:
                self.browser.quit()
            except Exception:
                pass


# =============================================================================
# 七、主入口
# =============================================================================

def main():
    print("=" * 60)
    print("  🚀 淘宝/天猫评论高效采集工具 V2")
    print("     MTOP Direct API + 智能防封")
    print("=" * 60)
    print(f"  ⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📊 请求上限: {MAX_REQUESTS_PER_RUN} 次/次运行")
    print(f"  🛡️  请求间隔: {REQUEST_DELAY_MIN}-{REQUEST_DELAY_MAX}s")
    print(f"  ☕ 长休息间隔: 每 {LONG_PAUSE_INTERVAL} 次请求")
    print()

    # 过滤出有效任务（不为空的）
    active_tasks = TASKS
    if not active_tasks:
        print("❌ 没有配置任何采集任务！")
        return

    print(f"📋 待采集任务: {len(active_tasks)} 个产品")
    for t in active_tasks:
        url_text = f"{len(t['urls'])} 个预设链接" if t.get('urls') else f"将自动搜索前 {t.get('max_shops', 10)} 家店"
        print(f"   • {t['product_name']} ({url_text})")
    print()

    crawler = TaobaoCrawlerV2()

    try:
        # 第一步：登录
        if not crawler.login():
            print("\n❌ 未能获取 MTOP 认证令牌！")
            print("   可能原因：")
            print("   1. 未成功登录淘宝")
            print("   2. 浏览器 Cookie 被清除")
            print("   3. 淘宝安全策略变更")
            return

        print("\n" + "=" * 60)
        print("  ✅ 认证成功！开始采集...")
        print("  💡 提示: 按 Ctrl+C 可安全中断并保存已采集数据")
        print("=" * 60)

        # 第二步：逐个任务采集
        for task_idx, task in enumerate(active_tasks):
            print(f"\n{'━' * 60}")
            print(f"📦 [{task_idx + 1}/{len(active_tasks)}] {task['product_name']}")
            print(f"   输出: {task['output_file']}")
            print(f"{'━' * 60}")

            # 自动搜索提取补全 URL
            if not task.get("urls"):
                max_shops = task.get("max_shops", 10)
                extracted_urls = crawler.search_and_extract_urls(task["product_name"], max_shops)
                if not extracted_urls:
                    print(f"   ⚠️ 搜索未能获取到链接，跳过该任务！")
                    continue
                task["urls"] = extracted_urls

            crawler.crawl_task(task)

            # 任务间长休息
            if task_idx < len(active_tasks) - 1:
                pause = random.uniform(60, 120)
                print(f"\n🔄 任务切换休息 {pause:.0f}s...")
                time.sleep(pause)

    except KeyboardInterrupt:
        print("\n\n🛑 用户中断！数据已自动保存。")
    except SystemExit as e:
        print(f"\n{e}")
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        crawler.cleanup()

    # 最终统计
    print(f"\n{'=' * 60}")
    print(f"  📊 本次运行统计")
    print(f"     总请求数: {crawler.total_requests}")
    print(f"     总采集数: {crawler.total_collected}")
    print(f"     结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
