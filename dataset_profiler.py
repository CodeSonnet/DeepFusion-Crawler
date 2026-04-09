#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  跨平台电商评论数据集特征分析脚本（Dataset Profiler）
==============================================================================
  用途：扫描 data/ 目录下所有平台的评论 JSON 文件，输出数据集的完整特征报告，
       包括字段覆盖、数据量九宫格、文本统计、评分分布、时间跨度等。

  使用方法：
      python dataset_profiler.py                     # 默认输出到控制台 + Markdown 文件
      python dataset_profiler.py --output report.md  # 指定输出文件名
      python dataset_profiler.py --data-dir ./data   # 指定数据目录

  设计理念：
      - 可复用：所有核心逻辑封装在函数和类中，方便后续 import 使用
      - 可扩展：新增平台或指标只需修改配置或添加分析函数
      - 对实验友好：输出格式兼容论文写作（Markdown 表格 + LaTeX 数据）
==============================================================================
"""

import json
import os
import re
import sys
import argparse
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


# =============================================================================
# 一、配置区：产品名称统一映射、平台目录映射
# =============================================================================

# 产品名称统一映射表（文件名关键词 -> 标准产品名）
PRODUCT_NAME_MAP = {
    "iphone17":         "iPhone 17 Pro",
    "iphone_17":        "iPhone 17 Pro",
    "huawei_p70":       "Huawei P70",
    "华为p70":          "Huawei P70",
    "华为P70":          "Huawei P70",
    "华为pura70":       "Huawei P70",      # Pura70 和 P70 视为同系列
    "pura70":           "Huawei P70",
    "xiaomi_15":        "Xiaomi 15 Pro",
    "小米15":           "Xiaomi 15 Pro",
    "vivo_x300":        "VIVO X300 Pro",
    "vivox300":         "VIVO X300 Pro",
    "oppo":             "OPPO Find X9 Pro",
    "oppofind":         "OPPO Find X9 Pro",
    "oppo_find":        "OPPO Find X9 Pro",
    "一加ace":          "OnePlus Ace 6T",
    "oneplus_ace":      "OnePlus Ace 6T",
    "一加ace6t":        "OnePlus Ace 6T",
    "ace6t":            "OnePlus Ace 6T",
    "redmi_k90":        "Redmi K90 Pro Max",
    "redmi-k90":        "Redmi K90 Pro Max",
    "redmik90":         "Redmi K90 Pro Max",
    "红米k90":          "Redmi K90 Pro Max",
    "iqoo_15":          "iQOO 15",
    "iqoo15":           "iQOO 15",
    "iqoo":             "iQOO 15",
    "magic7":           "Honor Magic7 Pro",
    "magic_7":          "Honor Magic7 Pro",
    "荣耀magic7":       "Honor Magic7 Pro",
    "荣耀magic":        "Honor Magic7 Pro",
    "honor":            "Honor Magic7 Pro",
    "realme":           "realme GT7 Pro",
    "realme_gt7":       "realme GT7 Pro",
    "realmegt7":        "realme GT7 Pro",
    "真我gt7":          "realme GT7 Pro",
    "gt7":              "realme GT7 Pro",
}

# 平台目录名 -> 标准平台名
PLATFORM_DIR_MAP = {
    "JD":        "京东",
    "TaoBao":    "淘宝/天猫",
    "Pinduoduo": "拼多多",
}

# 我们研究的 10 款产品（按品牌排序）
ALL_PRODUCTS = [
    "iPhone 17 Pro",
    "Huawei P70",
    "Xiaomi 15 Pro",
    "VIVO X300 Pro",
    "OPPO Find X9 Pro",
    "OnePlus Ace 6T",
    "Redmi K90 Pro Max",
    "iQOO 15",
    "Honor Magic7 Pro",
    "realme GT7 Pro",
]

# 所有平台列表
ALL_PLATFORMS = ["京东", "淘宝/天猫", "拼多多"]


# =============================================================================
# 二、工具函数
# =============================================================================

def normalize_product_name(filename: str) -> str:
    """
    根据文件名推断并返回标准化的产品名称。
    使用 PRODUCT_NAME_MAP 进行模糊匹配。
    """
    fn_lower = filename.lower().replace(" ", "_").replace("-", "_")
    for keyword, standard_name in PRODUCT_NAME_MAP.items():
        if keyword.lower().replace(" ", "_").replace("-", "_") in fn_lower:
            return standard_name
    # 如果无法识别，返回文件名本身作为产品名
    return filename


def parse_date(date_str: str) -> datetime | None:
    """
    解析多种格式的日期字符串，返回 datetime 对象。
    兼容 "2026-01-27 19:58:21"、"2026年3月17日"、"2026-01-19" 等格式。
    """
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y年%m月%d日",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y/%m/%d",
        "%Y/%m/%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # 尝试正则提取
    match = re.search(r"(\d{2,4})[年/-](\d{1,2})[月/-](\d{1,2})", date_str)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    return None


def count_sentences(text: str) -> int:
    """
    统计中文文本中的句子数量。
    使用中英文标点分句：。！？；\n 以及 .!?; 后跟空格的模式。
    """
    if not text or not isinstance(text, str):
        return 0
    # 按中文句末标点 + 英文句末标点分割
    sentences = re.split(r'[。！？；\n]+|[.!?;]\s+', text.strip())
    # 过滤空字符串
    sentences = [s.strip() for s in sentences if s.strip()]
    return max(len(sentences), 1) if text.strip() else 0


def count_chars(text: str) -> int:
    """统计文本字符数（去除空白）。"""
    if not text or not isinstance(text, str):
        return 0
    return len(text.strip())


def is_default_review(text: str) -> bool:
    """
    判断是否为默认好评 / 无意义评价。
    这些评价在训练前需要过滤。
    """
    if not text or not isinstance(text, str):
        return True
    text = text.strip()
    if len(text) == 0:
        return True

    default_patterns = [
        "此用户没有填写评价",
        "用户未填写评价内容",
        "默认好评",
        "系统默认好评",
        "用户未及时评价",
        "买家没有填写评价",
        "该用户没有填写评价",
    ]
    for pat in default_patterns:
        if pat in text:
            return True
    # 极短评论（<=2字）也视为无意义
    if len(text) <= 2:
        return True
    return False


# =============================================================================
# 三、核心分析类
# =============================================================================

class FileProfile:
    """单个数据文件的画像。"""

    def __init__(self, filepath: str, platform: str, product: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.platform = platform
        self.product = product
        self.file_size_bytes = os.path.getsize(filepath)

        # 加载数据
        with open(filepath, "r", encoding="utf-8") as f:
            self.data: list[dict] = json.load(f)

        self.total_reviews = len(self.data)

        # 字段分析
        self.all_fields: set[str] = set()
        self.field_coverage: dict[str, int] = Counter()  # 字段名 -> 非空计数
        self._analyze_fields()

        # 文本分析
        self.content_lengths: list[int] = []
        self.sentence_counts: list[int] = []
        self.default_review_count = 0
        self.has_append_count = 0
        self.has_images_count = 0
        self.has_reply_count = 0
        self._analyze_text()

        # 评分分析
        self.score_distribution: Counter = Counter()
        self._analyze_scores()

        # 时间分析
        self.dates: list[datetime] = []
        self._analyze_dates()

        # 投票/有用数分析
        self.votes: list[int] = []
        self._analyze_votes()

    def _analyze_fields(self):
        """分析字段覆盖度。"""
        for review in self.data:
            for key in review.keys():
                self.all_fields.add(key)
            for key in review.keys():
                val = review[key]
                if val is not None and val != "" and val != [] and val != 0:
                    self.field_coverage[key] += 1

    def _analyze_text(self):
        """分析评论文本特征。"""
        for review in self.data:
            content = review.get("content", "")

            # 默认好评检测
            if is_default_review(content):
                self.default_review_count += 1

            # 文本长度和句子数
            char_count = count_chars(content)
            sent_count = count_sentences(content)
            self.content_lengths.append(char_count)
            self.sentence_counts.append(sent_count)

            # 追评
            append = review.get("append_content", "")
            if append and isinstance(append, str) and append.strip():
                self.has_append_count += 1

            # 图片
            images = review.get("images", [])
            if images and isinstance(images, list) and len(images) > 0:
                self.has_images_count += 1

            # 商家回复
            reply = review.get("reply", "")
            if reply and isinstance(reply, str) and reply.strip():
                self.has_reply_count += 1

    def _analyze_scores(self):
        """分析评分分布。"""
        for review in self.data:
            score = review.get("score")
            if score is not None:
                try:
                    self.score_distribution[int(score)] += 1
                except (ValueError, TypeError):
                    self.score_distribution["无效"] += 1

    def _analyze_dates(self):
        """分析时间跨度。"""
        for review in self.data:
            date_str = review.get("date", "")
            dt = parse_date(date_str)
            if dt:
                self.dates.append(dt)

    def _analyze_votes(self):
        """分析点赞/有用数。"""
        for review in self.data:
            v = review.get("votes", 0)
            if v is not None:
                try:
                    self.votes.append(int(v))
                except (ValueError, TypeError):
                    pass

    # --- 统计属性 ---

    @property
    def avg_content_length(self) -> float:
        return statistics.mean(self.content_lengths) if self.content_lengths else 0

    @property
    def median_content_length(self) -> float:
        return statistics.median(self.content_lengths) if self.content_lengths else 0

    @property
    def avg_sentence_count(self) -> float:
        return statistics.mean(self.sentence_counts) if self.sentence_counts else 0

    @property
    def median_sentence_count(self) -> float:
        return statistics.median(self.sentence_counts) if self.sentence_counts else 0

    @property
    def avg_score(self) -> float:
        scores = []
        for s, cnt in self.score_distribution.items():
            if isinstance(s, int):
                scores.extend([s] * cnt)
        return statistics.mean(scores) if scores else 0

    @property
    def date_range(self) -> tuple[str, str] | None:
        if not self.dates:
            return None
        return (min(self.dates).strftime("%Y-%m-%d"), max(self.dates).strftime("%Y-%m-%d"))

    @property
    def default_review_rate(self) -> float:
        return self.default_review_count / self.total_reviews if self.total_reviews else 0

    @property
    def valid_review_count(self) -> int:
        return self.total_reviews - self.default_review_count


class DatasetProfiler:
    """整个数据集的分析器。"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.file_profiles: list[FileProfile] = []
        self._scan_and_load()

    def _scan_and_load(self):
        """扫描数据目录，加载所有 JSON 文件。"""
        for platform_dir, platform_name in PLATFORM_DIR_MAP.items():
            platform_path = os.path.join(self.data_dir, platform_dir)
            if not os.path.isdir(platform_path):
                print(f"[警告] 平台目录不存在: {platform_path}")
                continue

            for filename in sorted(os.listdir(platform_path)):
                if not filename.endswith(".json"):
                    continue
                filepath = os.path.join(platform_path, filename)
                product_name = normalize_product_name(filename)

                if product_name not in ALL_PRODUCTS:
                    print(f"  [跳过] {filename} (非目标产品: {product_name})")
                    continue

                print(f"  加载 [{platform_name}] {filename} -> {product_name}")
                profile = FileProfile(filepath, platform_name, product_name)
                self.file_profiles.append(profile)

    # --- 聚合查询 ---

    def get_profiles(self, platform: str, product: str) -> list[FileProfile]:
        """获取指定平台-产品的所有文件画像（同一产品可能有多个文件）。"""
        return [fp for fp in self.file_profiles
                if fp.platform == platform and fp.product == product]

    def get_merged_stats(self, platform: str, product: str) -> dict | None:
        """
        获取指定平台-产品的统计数据。
        当同平台同产品有多个文件时自动合并（通常每个产品只有一个文件）。
        返回 None 表示无数据（待爬）。
        """
        fps = self.get_profiles(platform, product)
        if not fps:
            return None

        # 合并各项统计
        total_reviews = sum(fp.total_reviews for fp in fps)
        valid_reviews = sum(fp.valid_review_count for fp in fps)
        default_count = sum(fp.default_review_count for fp in fps)
        all_lengths = []
        all_sents = []
        all_dates = []
        all_votes = []
        combined_scores = Counter()
        has_append = sum(fp.has_append_count for fp in fps)
        has_images = sum(fp.has_images_count for fp in fps)
        has_reply = sum(fp.has_reply_count for fp in fps)
        all_fields = set()
        field_coverage = Counter()

        for fp in fps:
            all_lengths.extend(fp.content_lengths)
            all_sents.extend(fp.sentence_counts)
            all_dates.extend(fp.dates)
            all_votes.extend(fp.votes)
            combined_scores += fp.score_distribution
            all_fields.update(fp.all_fields)
            field_coverage += fp.field_coverage

        avg_len = statistics.mean(all_lengths) if all_lengths else 0
        med_len = statistics.median(all_lengths) if all_lengths else 0
        avg_sent = statistics.mean(all_sents) if all_sents else 0
        med_sent = statistics.median(all_sents) if all_sents else 0

        score_vals = []
        for s in range(1, 6):
            score_vals.extend([s] * combined_scores[s])
        avg_score = statistics.mean(score_vals) if score_vals else 0

        date_range = None
        if all_dates:
            date_range = (min(all_dates).strftime("%Y-%m-%d"),
                          max(all_dates).strftime("%Y-%m-%d"))

        default_rate = default_count / total_reviews if total_reviews else 0

        return {
            "total_reviews": total_reviews,
            "valid_reviews": valid_reviews,
            "default_count": default_count,
            "default_rate": default_rate,
            "avg_content_length": avg_len,
            "median_content_length": med_len,
            "avg_sentence_count": avg_sent,
            "median_sentence_count": med_sent,
            "avg_score": avg_score,
            "score_distribution": combined_scores,
            "date_range": date_range,
            "has_append": has_append,
            "has_images": has_images,
            "has_reply": has_reply,
            "all_fields": all_fields,
            "field_coverage": field_coverage,
            "content_lengths": all_lengths,
            "sentence_counts": all_sents,
            "votes": all_votes,
            "file_count": len(fps),
        }

    def get_profiles_by_platform(self, platform: str) -> list[FileProfile]:
        return [fp for fp in self.file_profiles if fp.platform == platform]

    def get_profiles_by_product(self, product: str) -> list[FileProfile]:
        return [fp for fp in self.file_profiles if fp.product == product]

    @property
    def total_reviews(self) -> int:
        return sum(fp.total_reviews for fp in self.file_profiles)

    @property
    def total_valid_reviews(self) -> int:
        return sum(fp.valid_review_count for fp in self.file_profiles)

    @property
    def total_files(self) -> int:
        return len(self.file_profiles)

    @property
    def total_size_mb(self) -> float:
        return sum(fp.file_size_bytes for fp in self.file_profiles) / (1024 * 1024)

    @property
    def all_fields_union(self) -> set[str]:
        """所有文件字段的并集。"""
        fields = set()
        for fp in self.file_profiles:
            fields.update(fp.all_fields)
        return fields

    @property
    def all_fields_intersection(self) -> set[str]:
        """所有文件字段的交集。"""
        if not self.file_profiles:
            return set()
        fields = self.file_profiles[0].all_fields.copy()
        for fp in self.file_profiles[1:]:
            fields &= fp.all_fields
        return fields


# =============================================================================
# 四、报告生成
# =============================================================================

def generate_report(profiler: DatasetProfiler) -> str:
    """生成完整的 Markdown 格式报告。"""
    lines = []

    def ln(text=""):
        lines.append(text)

    # ---------------------------
    # 标题
    # ---------------------------
    ln("# 📊 跨平台电商评论数据集特征报告")
    ln()
    ln(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    ln(f"> 数据目录：`{profiler.data_dir}`")
    ln()

    # ---------------------------
    # 1. 数据集总览
    # ---------------------------
    ln("## 一、数据集总览")
    ln()
    ln(f"| 指标 | 值 |")
    ln(f"|:---|:---|")
    ln(f"| 覆盖平台数 | {len(ALL_PLATFORMS)} |")
    ln(f"| 目标产品数 | {len(ALL_PRODUCTS)} |")
    ln(f"| 数据文件数 | {profiler.total_files} |")
    ln(f"| **总评论数** | **{profiler.total_reviews:,}** |")
    ln(f"| 有效评论数（去除默认好评） | {profiler.total_valid_reviews:,} |")
    ln(f"| 默认/无意义评论数 | {profiler.total_reviews - profiler.total_valid_reviews:,} |")
    ln(f"| 数据集总大小 | {profiler.total_size_mb:.1f} MB |")
    ln()

    # ---------------------------
    # 2. 数据量九宫格（平台 × 产品）
    # ---------------------------
    ln("## 二、数据量九宫格（平台 × 产品）")
    ln()
    ln("### 2.1 总评论数")
    ln()

    # 表头
    header = "| 产品 \\\\ 平台 | " + " | ".join(ALL_PLATFORMS) + " | 合计 |"
    sep = "|:---|" + "|".join(["---:"] * len(ALL_PLATFORMS)) + "|---:|"
    ln(header)
    ln(sep)

    platform_totals = {p: 0 for p in ALL_PLATFORMS}
    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        product_total = 0
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms:
                row += f" {ms['total_reviews']:,} |"
                product_total += ms['total_reviews']
                platform_totals[platform] += ms['total_reviews']
            else:
                row += " ⏳ 待爬 |"
        row += f" {product_total:,} |" if product_total > 0 else " - |"
        ln(row)

    # 合计行
    grand_total = sum(platform_totals.values())
    totals_row = "| **合计** |"
    for p in ALL_PLATFORMS:
        totals_row += f" **{platform_totals[p]:,}** |"
    totals_row += f" **{grand_total:,}** |"
    ln(totals_row)
    ln()

    # 2.2 有效评论数九宫格
    ln("### 2.2 有效评论数（去除默认好评/空评论）")
    ln()
    header2 = "| 产品 \\\\ 平台 | " + " | ".join(ALL_PLATFORMS) + " | 合计 |"
    ln(header2)
    ln(sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        product_total = 0
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms:
                row += f" {ms['valid_reviews']:,} |"
                product_total += ms['valid_reviews']
            else:
                row += " ⏳ 待爬 |"
        row += f" {product_total:,} |" if product_total > 0 else " - |"
        ln(row)
    ln()

    # 2.3 默认好评率九宫格
    ln("### 2.3 默认好评/无意义评论比例")
    ln()
    header3 = "| 产品 \\\\ 平台 | " + " | ".join(ALL_PLATFORMS) + " |"
    sep3 = "|:---|" + "|".join(["---:"] * len(ALL_PLATFORMS)) + "|"
    ln(header3)
    ln(sep3)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms:
                row += f" {ms['default_rate']:.1%} |"
            else:
                row += " - |"
        ln(row)
    ln()

    # ---------------------------
    # 3. 字段覆盖度分析
    # ---------------------------
    ln("## 三、字段覆盖度分析")
    ln()

    # 各平台字段对比
    ln("### 3.1 各平台字段对比")
    ln()

    all_fields_sorted = sorted(profiler.all_fields_union)
    field_header = "| 字段 | " + " | ".join(ALL_PLATFORMS) + " | 说明 |"
    field_sep = "|:---|" + "|".join([":---:"] * len(ALL_PLATFORMS)) + "|:---|"
    ln(field_header)
    ln(field_sep)

    field_descriptions = {
        "platform": "数据来源平台",
        "product_name": "标准化产品名称",
        "id": "评论唯一标识",
        "content": "评论正文",
        "score": "星级评分 (1-5)",
        "date": "评论日期",
        "model_sku": "购买配置（颜色/容量）",
        "append_content": "追加评论",
        "votes": "点赞/有用数",
        "images": "买家秀图片URL列表",
        "reply": "商家回复",
        "goods_id": "商品ID（拼多多特有）",
    }

    for field in all_fields_sorted:
        row = f"| `{field}` |"
        for platform in ALL_PLATFORMS:
            fps = profiler.get_profiles_by_platform(platform)
            has_field = any(field in fp.all_fields for fp in fps)
            row += " ✅ |" if has_field else " ❌ |"
        desc = field_descriptions.get(field, "")
        row += f" {desc} |"
        ln(row)
    ln()

    # 3.2 字段非空率统计
    ln("### 3.2 各平台-产品字段非空率")
    ln()
    ln("以下统计每个文件中各字段实际有数据（非空、非空字符串、非空列表）的比例：")
    ln()

    key_fields = ["content", "score", "date", "model_sku", "append_content", "votes", "images", "reply"]

    for platform in ALL_PLATFORMS:
        fps = profiler.get_profiles_by_platform(platform)
        if not fps:
            continue
        ln(f"**{platform}**")
        ln()
        h = "| 文件 | " + " | ".join(key_fields) + " |"
        s = "|:---|" + "|".join(["---:"] * len(key_fields)) + "|"
        ln(h)
        ln(s)
        for fp in fps:
            row = f"| {fp.product} |"
            for field in key_fields:
                if field in fp.all_fields:
                    rate = fp.field_coverage.get(field, 0) / fp.total_reviews if fp.total_reviews else 0
                    row += f" {rate:.0%} |"
                else:
                    row += " N/A |"
            ln(row)
        ln()

    # ---------------------------
    # 4. 文本统计
    # ---------------------------
    ln("## 四、评论文本统计")
    ln()

    ln("### 4.1 评论长度统计（字符数）")
    ln()
    txt_header = "| 产品 \\\\ 平台 | " + " | ".join([f"{p} (均/中)" for p in ALL_PLATFORMS]) + " |"
    txt_sep = "|:---|" + "|".join(["---:"] * len(ALL_PLATFORMS)) + "|"
    ln(txt_header)
    ln(txt_sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms:
                row += f" {ms['avg_content_length']:.0f} / {ms['median_content_length']:.0f} |"
            else:
                row += " - |"
        ln(row)
    ln()

    ln("### 4.2 评论句子数统计")
    ln()
    sent_header = "| 产品 \\\\ 平台 | " + " | ".join([f"{p} (均/中)" for p in ALL_PLATFORMS]) + " |"
    ln(sent_header)
    ln(txt_sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms:
                row += f" {ms['avg_sentence_count']:.1f} / {ms['median_sentence_count']:.0f} |"
            else:
                row += " - |"
        ln(row)
    ln()

    # 平台级文本统计汇总
    ln("### 4.3 平台级文本统计汇总")
    ln()
    ln("| 平台 | 平均评论长度(字符) | 中位数评论长度 | 平均句子数 | 中位数句子数 | 追评率 | 带图率 | 有回复率 |")
    ln("|:---|---:|---:|---:|---:|---:|---:|---:|")

    for platform in ALL_PLATFORMS:
        fps = profiler.get_profiles_by_platform(platform)
        if not fps:
            ln(f"| {platform} | - | - | - | - | - | - | - |")
            continue

        all_lengths = []
        all_sents = []
        total_r = 0
        total_append = 0
        total_images = 0
        total_reply = 0

        for fp in fps:
            all_lengths.extend(fp.content_lengths)
            all_sents.extend(fp.sentence_counts)
            total_r += fp.total_reviews
            total_append += fp.has_append_count
            total_images += fp.has_images_count
            total_reply += fp.has_reply_count

        avg_len = statistics.mean(all_lengths) if all_lengths else 0
        med_len = statistics.median(all_lengths) if all_lengths else 0
        avg_sent = statistics.mean(all_sents) if all_sents else 0
        med_sent = statistics.median(all_sents) if all_sents else 0
        append_rate = total_append / total_r if total_r else 0
        image_rate = total_images / total_r if total_r else 0
        reply_rate = total_reply / total_r if total_r else 0

        ln(f"| {platform} | {avg_len:.1f} | {med_len:.0f} | {avg_sent:.2f} | {med_sent:.0f} | {append_rate:.1%} | {image_rate:.1%} | {reply_rate:.1%} |")
    ln()

    # ---------------------------
    # 5. 评分分析
    # ---------------------------
    ln("## 五、评分分布")
    ln()

    ln("### 5.1 各平台评分分布（百分比）")
    ln()
    ln("| 平台 | ⭐1 | ⭐2 | ⭐3 | ⭐4 | ⭐5 | 平均分 | 有评分率 |")
    ln("|:---|---:|---:|---:|---:|---:|---:|---:|")

    for platform in ALL_PLATFORMS:
        fps = profiler.get_profiles_by_platform(platform)
        if not fps:
            ln(f"| {platform} | - | - | - | - | - | - | - |")
            continue

        combined_scores = Counter()
        total_r = 0
        for fp in fps:
            combined_scores += fp.score_distribution
            total_r += fp.total_reviews

        total_scored = sum(combined_scores[i] for i in range(1, 6))
        scored_rate = total_scored / total_r if total_r else 0
        row = f"| {platform} |"
        for star in range(1, 6):
            pct = combined_scores[star] / total_scored * 100 if total_scored else 0
            row += f" {pct:.1f}% |"

        all_scores = []
        for s in range(1, 6):
            all_scores.extend([s] * combined_scores[s])
        avg_s = statistics.mean(all_scores) if all_scores else 0
        row += f" {avg_s:.2f} | {scored_rate:.1%} |"
        ln(row)
    ln()

    # 5.2 各产品评分分布
    ln("### 5.2 各产品平均评分（按平台）")
    ln()
    score_header = "| 产品 \\\\ 平台 | " + " | ".join(ALL_PLATFORMS) + " |"
    ln(score_header)
    ln(txt_sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms and ms['avg_score'] > 0:
                row += f" {ms['avg_score']:.2f} |"
            elif ms:
                row += " 无评分 |"
            else:
                row += " - |"
        ln(row)
    ln()

    # ---------------------------
    # 6. 时间跨度分析
    # ---------------------------
    ln("## 六、数据时间跨度")
    ln()
    ln("| 平台 | 产品 | 最早日期 | 最晚日期 | 跨度（天） |")
    ln("|:---|:---|:---|:---|---:|")

    for platform in ALL_PLATFORMS:
        for product in ALL_PRODUCTS:
            ms = profiler.get_merged_stats(platform, product)
            if not ms:
                ln(f"| {platform} | {product} | 待爬 | 待爬 | - |")
                continue
            dr = ms['date_range']
            if dr:
                d1 = datetime.strptime(dr[0], "%Y-%m-%d")
                d2 = datetime.strptime(dr[1], "%Y-%m-%d")
                span = (d2 - d1).days
                ln(f"| {platform} | {product} | {dr[0]} | {dr[1]} | {span} |")
            else:
                ln(f"| {platform} | {product} | 无法解析 | 无法解析 | - |")
    ln()

    # ---------------------------
    # 7. 数据文件清单
    # ---------------------------
    ln("## 七、数据文件清单")
    ln()
    ln("| # | 平台 | 产品 | 文件名 | 文件大小 | 评论数 | 有效评论数 |")
    ln("|---:|:---|:---|:---|---:|---:|---:|")

    for i, fp in enumerate(profiler.file_profiles, 1):
        size_kb = fp.file_size_bytes / 1024
        size_str = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        ln(f"| {i} | {fp.platform} | {fp.product} | `{fp.filename}` | {size_str} | {fp.total_reviews:,} | {fp.valid_review_count:,} |")
    ln()

    # ---------------------------
    # 8. 跨平台配对情况
    # ---------------------------
    ln("## 八、跨平台配对覆盖矩阵")
    ln()
    ln("对比学习需要同一产品在不同平台上的评论配对，以下矩阵展示各产品的跨平台覆盖情况：")
    ln()
    ln("| 产品 | " + " | ".join(ALL_PLATFORMS) + " | 配对状态 |")
    ln("|:---|" + "|".join([":---:"] * len(ALL_PLATFORMS)) + "|:---|")

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        available_platforms = []
        for platform in ALL_PLATFORMS:
            ms = profiler.get_merged_stats(platform, product)
            if ms:
                row += " ✅ |"
                available_platforms.append(platform)
            else:
                row += " ❌ |"

        n = len(available_platforms)
        if n >= 3:
            status = f"✅ 三平台配对（{n*(n-1)//2} 对）"
        elif n == 2:
            status = f"⚠️ 双平台配对（{' × '.join(available_platforms)}）"
        elif n == 1:
            status = "❌ 仅单平台，无法配对"
        else:
            status = "❌ 无数据"
        row += f" {status} |"
        ln(row)
    ln()

    # ---------------------------
    # 9. 实验相关总结
    # ---------------------------
    ln("## 九、对实验流程的关键发现与建议")
    ln()

    # 统计一些关键数据
    total_default = profiler.total_reviews - profiler.total_valid_reviews
    default_rate = total_default / profiler.total_reviews if profiler.total_reviews else 0

    # 配对产品数
    full_pair_count = 0
    partial_pair_count = 0
    for product in ALL_PRODUCTS:
        n_plat = sum(1 for p in ALL_PLATFORMS if profiler.get_merged_stats(p, product))
        if n_plat >= 3:
            full_pair_count += 1
        elif n_plat == 2:
            partial_pair_count += 1

    ln(f"1. **数据清洗**：数据集中有 {total_default:,} 条默认/无意义评论（占比 {default_rate:.1%}），训练前必须过滤。")
    ln(f"2. **跨平台配对**：{full_pair_count} 款产品有三平台数据，{partial_pair_count} 款仅双平台，对比学习的正样本构建以三平台产品为主。")
    ln(f"3. **产品名称统一**：拼多多的 `product_name` 字段为商品ID格式（如\"商品904664626870\"），需要在预处理阶段统一映射为标准产品名称。数据文件已完成去重合并与命名规范化。")

    # 检查评分覆盖
    no_score_files = [fp for fp in profiler.file_profiles if sum(fp.score_distribution[i] for i in range(1, 6)) == 0]
    if no_score_files:
        names = ", ".join([fp.filename for fp in no_score_files])
        ln(f"4. **评分缺失**：以下文件无有效评分数据：{names}，需要确认是否为采集遗漏。")

    # 检查日期格式混杂
    ln(f"5. **日期格式**：数据中混合了多种日期格式（`YYYY-MM-DD HH:MM:SS`、`YYYY年M月D日` 等），脚本已兼容解析，但建议在预处理阶段统一为 ISO 格式。")
    ln(f"6. **字段差异**：拼多多额外包含 `goods_id` 字段；三平台共有字段为 {len(profiler.all_fields_intersection)} 个，并集为 {len(profiler.all_fields_union)} 个。")

    # 附加：检查文本长度的极端值
    all_lengths = []
    for fp in profiler.file_profiles:
        all_lengths.extend(fp.content_lengths)
    if all_lengths:
        pct_short = sum(1 for l in all_lengths if l <= 10) / len(all_lengths)
        pct_long = sum(1 for l in all_lengths if l > 500) / len(all_lengths)
        ln(f"7. **文本长度分布**：极短评论（≤10字）占 {pct_short:.1%}，长评论（>500字）占 {pct_long:.1%}。BERTopic 和 DeBERTa 编码前建议设定合理的长度阈值。")

    ln()
    ln("---")
    ln("*本报告由 `dataset_profiler.py` 自动生成，如需更新请重新运行脚本。*")

    return "\n".join(lines)


# =============================================================================
# 五、主入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="跨平台电商评论数据集特征分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
        help="数据目录路径（默认为脚本同级的 data/ 目录）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="dataset_report.md",
        help="输出报告的文件名（默认 dataset_report.md）",
    )
    parser.add_argument(
        "--no-file",
        action="store_true",
        help="仅输出到控制台，不生成文件",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  跨平台电商评论数据集特征分析")
    print("=" * 60)
    print(f"  数据目录: {args.data_dir}")
    print()

    # 加载并分析
    profiler = DatasetProfiler(args.data_dir)

    print()
    print(f"  扫描完成: 共加载 {profiler.total_files} 个文件, {profiler.total_reviews:,} 条评论")
    print()

    # 生成报告
    report = generate_report(profiler)

    # 输出
    if not args.no_file:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  ✅ 报告已保存: {output_path}")
    else:
        print(report)

    print()
    print("完成！")


if __name__ == "__main__":
    main()
