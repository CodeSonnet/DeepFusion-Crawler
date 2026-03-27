"""
拼多多评论爬虫 - 一键抓取
输入商品名称，自动搜索商品 → 获取ID → 收集评论
"""

import requests
import json
import time
import random
import hashlib
import re
import os
import sys


# ==================== 配置区（从F12复制Cookie） ====================
COOKIE = """{YOUR_COOKIE}"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    "Referer": "https://mobile.yangkeduo.com/",
    "Cookie": COOKIE,
}


# ==================== 爬虫类 ====================

class PinduoduoCrawler:
    """拼多多爬虫"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._parse_cookies(COOKIE)

    def _parse_cookies(self, cookie_str):
        for item in cookie_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.session.cookies[key.strip()] = value.strip()

    def search_goods_from_html(self, keyword):
        """从搜索结果HTML页面提取商品ID"""
        import re
        url = f"https://mobile.yangkeduo.com/search_result.html?search_key={keyword}"

        resp = self.session.get(url, timeout=10)
        if resp.status_code == 200:
            html = resp.text
            # 从HTML中提取 goods_id=数字& 模式的商品ID
            goods_ids = re.findall(r'goods_id=(\d+)&', html)
            # 去重
            unique_ids = list(dict.fromkeys(goods_ids))
            return unique_ids
        return []

    def search_goods(self, keyword, page=1, size=20):
        """搜索商品（兼容旧接口，仍使用API）"""
        url = "http://apiv3.yangkeduo.com/v5/goods"
        params = {"page": page, "size": min(size, 400), "q": keyword}

        resp = self.session.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('goods_list', []), data.get('has_more', False)
        return [], False

    def get_reviews(self, goods_id, page=1, size=20):
        """获取评论"""
        url = f"http://apiv3.yangkeduo.com/reviews/{goods_id}/list"
        params = {"page": page, "size": min(size, 20)}

        resp = self.session.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('data', [])
        return []

    def search_and_get_reviews(self, keyword, max_goods=10, max_pages_per_goods=50):
        """
        搜索商品并获取评论

        Args:
            keyword: 商品关键词
            max_goods: 最多抓取几个商品的评论
            max_pages_per_goods: 每个商品最多抓取几页评论
        """
        print(f"\n{'='*60}")
        print(f"开始抓取: {keyword}")
        print(f"{'='*60}\n")

        # Step 1: 从HTML页面提取商品ID
        print(f"[1/3] 搜索商品: {keyword}")
        goods_ids = self.search_goods_from_html(keyword)
        print(f"  找到 {len(goods_ids)} 个商品ID")

        # 转换为goods_list格式
        goods_list = []
        for gid in goods_ids[:max_goods]:
            goods_list.append({
                'goods_id': gid,
                'goods_name': f'商品{gid}',
                'price': 0,
                'sales': '',
            })

        goods_list = goods_list[:max_goods]
        print(f"  搜索完成，共找到 {len(goods_list)} 款商品\n")

        # Step 2: 收集评论
        print(f"[2/3] 收集评论 (共 {len(goods_list)} 个商品)")
        all_reviews = []

        for i, goods in enumerate(goods_list):
            gid = goods['goods_id']
            gname = goods['goods_name'][:30]

            print(f"\n  [{i+1}/{len(goods_list)}] {gname}...")
            reviews_count = 0

            for page in range(1, max_pages_per_goods + 1):
                reviews = self.get_reviews(gid, page=page)

                if not reviews:
                    break

                for r in reviews:
                    parsed = self._parse_review(r, goods['goods_name'])
                    all_reviews.append(parsed)
                    reviews_count += 1

                print(f"    第{page}页: +{len(reviews)} 条", end="")

                if len(reviews) < 20:
                    print(" (最后一页)")
                    break

                time.sleep(random.uniform(0.2, 0.5))

            print(f"    共 {reviews_count} 条评论")

            # 随机延迟
            time.sleep(random.uniform(0.5, 1.5))

        # Step 3: 保存
        print(f"\n[3/3] 保存数据")
        self._save(all_reviews, keyword)

        print(f"\n{'='*60}")
        print(f"抓取完成!")
        print(f"  商品数量: {len(goods_list)}")
        print(f"  评论总数: {len(all_reviews)}")
        print(f"{'='*60}")

        return all_reviews, goods_list

    def _parse_review(self, review, goods_name=''):
        """解析单条评论"""
        # 规格
        specs = review.get('specs', '') or review.get('orderSpecsString', '')
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
        replies = [r.get('content', '') for r in reply_list if isinstance(r, dict) and r.get('content')]
        reply = '; '.join(replies)

        # 图片
        pictures = [p.get('url', '') for p in review.get('pictures', []) or [] if isinstance(p, dict)]

        return {
            'id': review.get('review_id') or self._make_id(review),
            'content': review.get('comment', ''),
            'score': review.get('desc_score') or review.get('stars', 0),
            'date': time_str,
            'model_sku': specs,
            'append_content': review.get('appendComment', ''),
            'votes': review.get('favor_count', 0),
            'images': pictures,
            'reply': reply,
            'platform': 'Pinduoduo',
            'product_name': goods_name,
            'goods_id': review.get('goods_id', ''),
        }

    def _make_id(self, review):
        content = review.get('comment', '')
        name = review.get('name', '')
        raw = f"{content}|{name}|pdd"
        return hashlib.md5(raw.encode()).hexdigest[:16]

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
    if len(sys.argv) < 2:
        print("\n" + "="*50)
        print("拼多多评论爬虫")
        print("="*50)
        print("\n使用方法:")
        print("  python pdd_comment_crawler.py 商品名称")
        print("\n示例:")
        print('  python pdd_comment_crawler.py "华为Pura70"')
        print('  python pdd_comment_crawler.py "充电宝"')
        print("\n提示: 评论数据将保存到 data/Pinduoduo/ 目录")
        print("="*50 + "\n")
        sys.exit(1)

    keyword = sys.argv[1]
    crawler = PinduoduoCrawler()
    crawler.search_and_get_reviews(keyword)
