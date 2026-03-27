"""
拼多多爬虫 - 整合搜索+评论抓取
"""

import requests
import json
import time
import random
import hashlib
import re
import os


class PinduoduoCrawler:
    """拼多多爬虫"""

    def __init__(self, cookies=None, headers=None):
        self.cookies = cookies or ""
        self.headers = headers or self._default_headers()
        self.session = requests.Session()
        self.session.cookies.update(self._parse_cookies(self.cookies))

    def _default_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Referer": "https://mobile.yangkeduo.com/",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _parse_cookies(self, cookie_str):
        cookies = {}
        if cookie_str:
            for item in cookie_str.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
        return cookies

    # ==================== 搜索商品 ====================

    def search_goods(self, keyword, page=1, size=20):
        """
        搜索商品

        Args:
            keyword: 搜索关键词
            page: 页码
            size: 每页数量

        Returns:
            商品列表
        """
        url = f"http://apiv3.yangkeduo.com/v5/goods"
        params = {
            "page": page,
            "size": min(size, 400),
            "q": keyword
        }

        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                goods_list = data.get('goods_list', [])
                return {
                    'goods': goods_list,
                    'total': data.get('total_size', 0),
                    'has_more': data.get('has_more', False)
                }
        except Exception as e:
            print(f"搜索失败: {e}")
        return {'goods': [], 'total': 0, 'has_more': False}

    def search_all_goods(self, keyword, max_pages=10, size=20):
        """
        搜索所有商品

        Args:
            keyword: 搜索关键词
            max_pages: 最大页数
            size: 每页数量

        Returns:
            所有商品列表
        """
        all_goods = []
        seen_ids = set()

        print(f"搜索关键词: {keyword}")
        print("-" * 50)

        for page in range(1, max_pages + 1):
            print(f"搜索第 {page} 页...", end=" ")

            result = self.search_goods(keyword, page=page, size=size)
            goods = result.get('goods', [])

            if not goods:
                print("无数据")
                break

            new_count = 0
            for g in goods:
                gid = g.get('goods_id', '')
                if gid not in seen_ids:
                    seen_ids.add(gid)
                    all_goods.append({
                        'goods_id': gid,
                        'goods_name': g.get('goods_name', ''),
                        'price': g.get('price', 0) / 100 if g.get('price') else 0,
                        'sales': g.get('sales', 0),
                        'mall_name': g.get('mall_name', ''),
                        'link': f"https://mobile.yangkeduo.com/goods.html?goods_id={gid}"
                    })
                    new_count += 1

            print(f"新增 {new_count} 款，累计 {len(all_goods)} 款")

            if not result.get('has_more'):
                print("已到最后一页")
                break

            time.sleep(random.uniform(0.5, 1.5))

        print("-" * 50)
        print(f"搜索完成，共 {len(all_goods)} 款商品")

        return all_goods

    # ==================== 获取评论 ====================

    def get_reviews(self, goods_id, page=1, size=20):
        """
        获取单页评论

        Args:
            goods_id: 商品ID
            page: 页码
            size: 每页数量（最多20）

        Returns:
            评论列表
        """
        url = f"http://apiv3.yangkeduo.com/reviews/{goods_id}/list"
        params = {
            "size": min(size, 20),
            "page": page
        }

        try:
            response = self.session.get(url, params=params, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
        except Exception as e:
            print(f"获取评论失败: {e}")
        return []

    def get_all_reviews(self, goods_id, max_pages=100, size=20):
        """
        获取所有评论

        Args:
            goods_id: 商品ID
            max_pages: 最大页数
            size: 每页数量

        Returns:
            所有评论列表
        """
        all_reviews = []
        seen_ids = set()

        print(f"  抓取商品 {goods_id} 的评论...")
        print(f"  每页 {size} 条，最大 {max_pages} 页")

        for page in range(1, max_pages + 1):
            reviews = self.get_reviews(goods_id, page=page, size=size)

            if not reviews:
                break

            new_count = 0
            for review in reviews:
                rid = review.get('review_id') or self._make_id(review)
                if rid not in seen_ids:
                    seen_ids.add(rid)
                    all_reviews.append(self._parse_review(review))
                    new_count += 1

            print(f"    第{page}页: 新增 {new_count} 条，累计 {len(all_reviews)} 条")

            if len(reviews) < size:
                break

            time.sleep(random.uniform(0.3, 1.0))

        return all_reviews

    def _make_id(self, review):
        content = review.get('comment', '')
        name = review.get('name', '')
        raw = f"{content}|{name}|pdd"
        return hashlib.md5(raw.encode()).hexdigest[:16]

    def _parse_review(self, review):
        """解析评论"""
        # 规格
        specs = review.get('specs', '')
        if isinstance(specs, str):
            try:
                specs_list = json.loads(specs)
                specs = '; '.join([f"{s.get('spec_key','')}:{s.get('spec_value','')}" for s in specs_list])
            except:
                pass

        # 时间戳
        time_str = review.get('time', '')
        if isinstance(time_str, (int, float)):
            try:
                import datetime
                time_str = datetime.datetime.fromtimestamp(time_str).strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass

        # 回复
        reply_list = review.get('reply_list', []) or []
        replies = [r.get('content', '') if isinstance(r, dict) else str(r) for r in reply_list if r.get('content')]
        reply = '; '.join(replies)

        # 图片
        pictures = [p.get('url', '') if isinstance(p, dict) else str(p) for p in review.get('pictures', []) or []]

        return {
            'id': review.get('review_id') or self._make_id(review),
            'content': review.get('comment', ''),
            'score': review.get('desc_score') or review.get('stars', 0),
            'date': time_str,
            'model_sku': specs or review.get('orderSpecsString', ''),
            'append_content': review.get('appendComment', ''),
            'votes': review.get('favor_count', 0),
            'images': pictures,
            'reply': reply,
            'platform': 'Pinduoduo',
            'product_name': '',
            'goods_id': review.get('goods_id', ''),
        }


def save_json(data, filename, output_dir='../data/Pinduoduo'):
    """保存JSON"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"保存到: {path}")
    return path


# ==================== 配置 ====================

COOKIE = """api_uid=Cix7XGm/hSmWJQBwXKrVAg==; _nano_fp=Xpm8n0gylpgYn5PqX9_v6MOK1eZp1IS42L2tg_75; webp=1; dilx=L0b~gVJ~8iH5qnUFYA~Wp; PDDAccessToken=H6POWQ7PDVTH5S5WSB4QAQHYYKGG5C52JDOQLSBC4APC5YFHKXFA120c03d; pdd_user_id=5395692311744; pdd_user_uin=ZP4NEYZLP4CZYAGTX5UFR6S4MU_GEXDA; cui_glyph_baseFontSize=106.667; jrpl=B0IYDNEgtY3PVVLzjPHq1wqx0VUwnLyb; njrpl=B0IYDNEgtY3PVVLzjPHq1wqx0VUwnLyb; pdd_vds=gaTcBxNcsTLcuBllmdNLxLxlGuBmNlLLmTsbTNnmBxIbLwubLcdBGubLBDLf"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    "Referer": "https://mobile.yangkeduo.com/",
}


# ==================== 主程序 ====================

if __name__ == '__main__':
    import sys

    crawler = PinduoduoCrawler(cookies=COOKIE, headers=HEADERS)

    if len(sys.argv) > 1:
        mode = sys.argv[1]

        if mode == 'search':
            # 搜索模式
            keyword = sys.argv[2] if len(sys.argv) > 2 else "华为pura70"
            goods = crawler.search_all_goods(keyword, max_pages=5)
            save_json(goods, f"search_{keyword}.json")

        elif mode == 'reviews':
            # 评论模式
            goods_id = sys.argv[2] if len(sys.argv) > 2 else "921751342960"
            reviews = crawler.get_all_reviews(goods_id, max_pages=50)
            save_json(reviews, f"reviews_{goods_id}.json")

        elif mode == 'all':
            # 搜索+评论模式
            keyword = sys.argv[2] if len(sys.argv) > 2 else "华为pura70"
            goods = crawler.search_all_goods(keyword, max_pages=3)

            all_reviews = []
            for i, g in enumerate(goods[:5]):  # 只抓前5个商品
                print(f"\n[{i+1}/{min(5, len(goods))}] 处理商品: {g['goods_name']}")
                reviews = crawler.get_all_reviews(g['goods_id'], max_pages=20)
                for r in reviews:
                    r['product_name'] = g['goods_name']
                all_reviews.extend(reviews)

            save_json(all_reviews, f"all_reviews_{keyword}.json")

    else:
        print("""
拼多多爬虫使用方法:

  搜索商品:
    python PDD_Crawler_Script.py search "关键词"

  获取评论:
    python PDD_Crawler_Script.py reviews "商品ID"

  搜索+抓取评论:
    python PDD_Crawler_Script.py all "关键词"

示例:
  python PDD_Crawler_Script.py search "华为pura70"
  python PDD_Crawler_Script.py reviews 921751342960
  python PDD_Crawler_Script.py all "充电宝"
""")
