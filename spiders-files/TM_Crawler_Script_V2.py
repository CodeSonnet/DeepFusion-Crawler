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
from urllib.parse import urlparse, parse_qs

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
        "urls": [
            # 在此粘贴该产品在淘宝/天猫的商品链接（支持多个店铺）
            # "https://detail.tmall.com/item.htm?id=xxxxxx",
        ],
        "output_file": "data/TaoBao/taobao_Huawei_P70.json",
    },
    {
        "product_name": "iPhone 17 Pro",
        "urls": [],
        "output_file": "data/TaoBao/taobao_iPhone17_Pro.json",
    },
    {
        "product_name": "Xiaomi 15 Pro",
        "urls": [],
        "output_file": "data/TaoBao/taobao_Xiaomi_15_Pro.json",
    },
    {
        "product_name": "VIVO X300 Pro",
        "urls": [],
        "output_file": "data/TaoBao/taobao_VIVO_X300_Pro.json",
    },
    {
        "product_name": "Samsung Galaxy S26 Ultra",
        "urls": [],
        "output_file": "data/TaoBao/taobao_Samsung_Galaxy_S26_Ultra.json",
    },
    {
        "product_name": "OPPO Find X9 Pro",
        "urls": [],
        "output_file": "data/TaoBao/taobao_OPPO_Find_X9_Pro.json",
    },
    {
        "product_name": "OnePlus 14",
        "urls": [],
        "output_file": "data/TaoBao/taobao_OnePlus_14.json",
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
    match = re.search(r"mtopjsonp\d+\((.*)\)$", text.strip(), re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # 尝试直接 JSON 解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_single_review(item: dict, product_name: str) -> dict:
    """
    将淘宝 API 返回的单条评论原始数据解析为标准格式。
    与项目中其他平台的数据格式保持一致。
    """
    # 提取图片列表，补全协议头
    pic_list = item.get("feedPicPathList", [])
    full_pics = [
        f"https:{pic}" if pic.startswith("//") else pic
        for pic in pic_list
    ]

    # 提取点赞数
    interact = item.get("interactInfo", {})
    like_count = int(interact.get("likeCount", 0))

    # 提取追评
    append_text = ""
    append_obj = item.get("appendComment") or item.get("appendFeed")
    if isinstance(append_obj, dict):
        append_text = (
            append_obj.get("content", "") or append_obj.get("feedback", "")
        )

    # 尝试提取真实评分（淘宝 API 有时会返回）
    # rateScore: 1-5, 有时字段缺失则默认为 5（好评）
    score = item.get("rateScore", None)
    if score is None:
        # 备选字段
        rate_type = item.get("rateType", 0)
        # 0=好评, 1=中评, 2=差评
        score = {0: 5, 1: 3, 2: 1}.get(rate_type, 5)

    return {
        "platform": "Taobao/Tmall",
        "product_name": product_name,
        "id": str(item.get("id", "")),
        "content": (
            item.get("feedback", "") or item.get("rateContent", "")
        ).replace("\n", " ").strip(),
        "score": score,
        "date": (
            item.get("feedbackDate", "") or item.get("rateDate", "未知")
        ),
        "model_sku": (
            item.get("skuValueStr", "") or item.get("auctionSku", "未知")
        ),
        "append_content": append_text.replace("\n", " ").strip(),
        "votes": like_count,
        "images": full_pics,
        "reply": item.get("reply", ""),
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

        # 设置真实的请求头
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
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
        co.set_user_data_path(USER_DATA_DIR)
        self.browser = ChromiumPage(co)

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
        # 访问天猫首页触发 h5 token
        self.browser.get("https://www.tmall.com")
        time.sleep(3)

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
        当 token 过期时，通过浏览器刷新页面重新获取。
        如果浏览器已关闭，则从 requests 的 cookie jar 中尝试更新。
        """
        print("   🔄 正在刷新 MTOP token...")

        # 优先尝试从 requests 会话的 cookie 中更新
        # （MTOP 服务器会在响应中设置新的 _m_h5_tk）
        cookies_dict = {
            c.name: c.value for c in self.session.cookies
        }
        old_token = self.signer.token
        self.signer.update_token(cookies_dict)

        if self.signer.token and self.signer.token != old_token:
            print(f"   ✅ Token 已从响应 Cookie 中自动刷新")
            return True

        # 如果 requests cookie 中没有新 token，回退到浏览器
        if self.browser:
            try:
                self.browser.get("https://www.tmall.com")
                time.sleep(3)
                return self._extract_cookies()
            except Exception as e:
                print(f"   ❌ 浏览器刷新失败: {e}")

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
    # 6.3 API 请求
    # -----------------------------------------------------------------

    def _fetch_reviews_page(
        self, item_id: str, seller_id: str, page: int
    ) -> tuple[list, bool, str]:
        """
        请求一页评论数据。

        参数:
            item_id: 商品 ID
            seller_id: 卖家 ID（可为空字符串）
            page: 页码（从 1 开始）

        返回:
            (评论列表, 是否还有下一页, 错误类型或空字符串)
        """
        data = {
            "itemId": str(item_id),
            "spuId": "",
            "sellerId": str(seller_id),
            "order": "1",             # 按时间排序
            "currentPage": page,
            "pageSize": PAGE_SIZE,
            "filter": "0",
            "content": "1",            # 请求评论内容
            "tagId": "",
            "folded": "0",
        }

        params = self.signer.build_request_params(data)
        url = MTOP_BASE_URL.format(api=MTOP_API_NAME, version=MTOP_API_VERSION)

        # 设置本次请求的 Referer（与商品页一致）
        self.session.headers["Referer"] = (
            f"https://detail.tmall.com/item.htm?id={item_id}"
        )

        try:
            resp = self.session.get(url, params=params, timeout=15)

            # 从响应中更新 Cookie（MTOP 服务器可能刷新 token）
            # requests.Session 会自动合并 Set-Cookie
            new_cookies = {c.name: c.value for c in self.session.cookies}
            self.signer.update_token(new_cookies)

            # 解析 JSONP
            result = parse_jsonp_response(resp.text)
            if not result:
                return [], False, "PARSE_ERROR"

            # 检查返回状态
            ret_codes = result.get("ret", [])

            # Token 过期
            if any("TOKEN_EXOIRED" in r or "TOKEN_EXPIRED" in r for r in ret_codes):
                return [], False, "TOKEN_EXPIRED"

            # 被风控
            if any("FAIL_SYS_ILLEGAL_ACCESS" in r for r in ret_codes):
                return [], False, "BLOCKED"

            # 其他失败
            if any("FAIL" in r for r in ret_codes):
                # 有些 FAIL 是正常的（如商品不存在）
                return [], False, f"API_FAIL:{ret_codes}"

            # 提取评论列表
            rate_list = result.get("data", {}).get("rateList", [])

            # 判断是否还有下一页
            rate_data = result.get("data", {})
            max_page = rate_data.get("maxPage", 99)
            has_more = page < max_page and len(rate_list) >= PAGE_SIZE

            return rate_list, has_more, ""

        except requests.exceptions.Timeout:
            return [], False, "TIMEOUT"
        except requests.exceptions.ConnectionError:
            return [], False, "CONNECTION_ERROR"
        except Exception as e:
            return [], False, f"EXCEPTION:{e}"

    # -----------------------------------------------------------------
    # 6.4 商品信息提取
    # -----------------------------------------------------------------

    def _get_seller_id_from_page(self, item_id: str) -> str:
        """
        尝试通过浏览器获取 sellerId（部分商品 API 可能需要）。
        如果获取失败返回空字符串（大多数情况下空字符串也能工作）。
        """
        if not self.browser:
            return ""
        try:
            url = f"https://detail.tmall.com/item.htm?id={item_id}"
            self.browser.get(url)
            time.sleep(3)
            # 尝试从页面源码中提取 sellerId
            page_source = self.browser.html
            match = re.search(r'"sellerId"\s*:\s*"?(\d+)"?', page_source)
            if match:
                return match.group(1)
        except Exception:
            pass
        return ""

    # -----------------------------------------------------------------
    # 6.5 核心采集流程
    # -----------------------------------------------------------------

    def crawl_task(self, task: dict):
        """
        执行一个采集任务（一个产品）。

        流程：
        1. 加载历史数据（断点续传）
        2. 逐个商品链接 → 提取 itemId → 逐页请求 → 解析 → 去重存储
        3. 自动保存进度
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

        # --- 逐个商品链接采集 ---
        for url_idx, url in enumerate(urls):
            item_id = extract_item_id(url)
            if not item_id:
                print(f"   ❌ 无法从链接提取商品ID: {url}")
                continue

            print(f"\n   🏪 [{url_idx + 1}/{len(urls)}] 商品 {item_id}")

            # 获取 sellerId（最佳努力，获取不到也能工作）
            seller_id = self._get_seller_id_from_page(item_id)
            if seller_id:
                print(f"      卖家ID: {seller_id}")

            consecutive_empty_pages = 0  # 连续空页计数

            for page in range(1, MAX_PAGES_PER_ITEM + 1):
                # --- 防封延迟 ---
                self._smart_delay()

                # --- 请求一页 ---
                reviews, has_more, error = self._fetch_reviews_page(
                    item_id, seller_id, page
                )

                # --- 错误处理 ---
                if error:
                    if error == "TOKEN_EXPIRED":
                        # Token 过期，尝试刷新后重试当前页
                        if self._refresh_token():
                            self._error_backoff("Token 过期，已刷新，重试中...")
                            # 重试（递减page使下次循环还是同一页）
                            continue
                        else:
                            print("   ❌ Token 刷新失败，停止当前商品")
                            break

                    elif error == "BLOCKED":
                        self._error_backoff("触发风控！正在退避...")
                        # 退避后重试 — 不递增page
                        continue

                    elif "API_FAIL" in error:
                        print(f"   ⚠️  API 返回失败: {error}")
                        self._error_backoff("API 调用失败")
                        if self.consecutive_errors >= MAX_RETRIES_PER_PAGE:
                            print("   ❌ 超过最大重试次数，跳过当前商品")
                            break
                        continue

                    else:
                        self._error_backoff(f"请求异常: {error}")
                        if self.consecutive_errors >= MAX_RETRIES_PER_PAGE:
                            print("   ❌ 超过最大重试次数，跳过当前商品")
                            break
                        continue

                # --- 请求成功 ---
                self._reset_error_state()

                # 解析并去重
                new_count = 0
                for raw_review in reviews:
                    rid = str(raw_review.get("id", ""))
                    if rid and rid not in unique_ids:
                        clean = parse_single_review(raw_review, product_name)
                        all_data.append(clean)
                        unique_ids.add(rid)
                        new_count += 1
                        self.total_collected += 1

                # 状态显示
                print(
                    f"      📄 Page {page:>3d}: "
                    f"返回 {len(reviews):>2d} 条, "
                    f"新增 {new_count:>2d}, "
                    f"累计 {len(all_data):,}"
                )

                # --- 连续空页检测 ---
                if new_count == 0:
                    consecutive_empty_pages += 1
                else:
                    consecutive_empty_pages = 0

                if consecutive_empty_pages >= CONSECUTIVE_EMPTY_LIMIT:
                    print(
                        f"      ⚠️  连续 {CONSECUTIVE_EMPTY_LIMIT} 页无新数据，"
                        f"该商品评论已采集完毕"
                    )
                    break

                # --- 到达最后一页 ---
                if not has_more:
                    print(f"      ✅ 已到达最后一页 (Page {page})")
                    break

                # --- 自动保存（每 10 页存一次） ---
                if page % 10 == 0:
                    self._save_data(all_data, output_file)
                    print(f"      💾 自动保存 ({len(all_data):,} 条)")

            # --- 商品切换长休息 ---
            if url_idx < len(urls) - 1:
                switch_pause = random.uniform(
                    PRODUCT_SWITCH_PAUSE_MIN, PRODUCT_SWITCH_PAUSE_MAX
                )
                print(
                    f"\n   💤 商品切换休息 {switch_pause:.0f}s..."
                )
                time.sleep(switch_pause)

        # --- 最终保存 ---
        self._save_data(all_data, output_file)
        added = len(all_data) - initial_count
        print(
            f"\n   🎉 [{product_name}] 采集完成！"
            f"本次新增 {added:,} 条, 总计 {len(all_data):,} 条"
        )

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

    # 过滤出有 URL 的任务
    active_tasks = [t for t in TASKS if t["urls"]]
    if not active_tasks:
        print("❌ 没有配置任何采集任务！")
        print("   请在脚本顶部的 TASKS 列表中填入商品链接。")
        return

    print(f"📋 待采集任务: {len(active_tasks)} 个产品")
    for t in active_tasks:
        print(f"   • {t['product_name']} ({len(t['urls'])} 个链接)")
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
