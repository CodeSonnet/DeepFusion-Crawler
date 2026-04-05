#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
  跨平台电商评论数据有效性验证脚本（Data Relevance Validator）
==============================================================================
  用途：扫描 data/ 目录下所有平台的评论 JSON 文件，从多维度检测每条评论
       是否真正属于其声称的目标产品，识别因搜索推荐机制混入的无关评论。

  使用方法：
      python data_relevance_validator.py                     # 默认输出报告
      python data_relevance_validator.py --output report.md  # 指定输出文件名
      python data_relevance_validator.py --data-dir ./data   # 指定数据目录
      python data_relevance_validator.py --export-suspects   # 导出可疑评论明细

  验证维度：
      1. SKU关键词匹配 — model_sku 是否包含目标产品的品牌/型号关键词
      2. 品牌信号冲突 — 评论内容或SKU是否提到了完全不同品牌的产品
      3. product_name一致性 — 同一文件内product_name字段是否出现多个值
      4. 型号关键词匹配 — 评论内容中提到的型号是否与目标产品一致
      5. 综合置信度评分 — 多信号加权得出每条评论的"归属置信度"

  设计理念：
      - 与 dataset_profiler.py 互补，专注"数据有效性"分析维度
      - 输出可直接用于数据清洗流水线的可疑评论列表
      - 每种检测规则独立封装，方便新增/调整
==============================================================================
"""

import json
import os
import re
import argparse
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


# =============================================================================
# 一、配置区
# =============================================================================

# 产品名称统一映射表（与 dataset_profiler.py 保持一致）
PRODUCT_NAME_MAP = {
    "iphone17":         "iPhone 17 Pro",
    "iphone_17":        "iPhone 17 Pro",
    "huawei_p70":       "Huawei P70",
    "华为p70":          "Huawei P70",
    "华为P70":          "Huawei P70",
    "华为pura70":       "Huawei P70",
    "pura70":           "Huawei P70",
    "xiaomi_15":        "Xiaomi 15 Pro",
    "小米15":           "Xiaomi 15 Pro",
    "vivo_x300":        "VIVO X300 Pro",
    "vivox300":         "VIVO X300 Pro",
    "oppo":             "OPPO Find X9 Pro",
    "oppofind":         "OPPO Find X9 Pro",
    "oppo_find":        "OPPO Find X9 Pro",
    "oneplus":          "OnePlus 14",
    "一加":             "OnePlus 14",
    "一加14":           "OnePlus 14",
}

# 平台目录名 -> 标准平台名
PLATFORM_DIR_MAP = {
    "JD":        "京东",
    "TaoBao":    "淘宝/天猫",
    "Pinduoduo": "拼多多",
}

# 所有目标产品
ALL_PRODUCTS = [
    "iPhone 17 Pro",
    "Huawei P70",
    "Xiaomi 15 Pro",
    "VIVO X300 Pro",
    "OPPO Find X9 Pro",
    "OnePlus 14",
]

ALL_PLATFORMS = ["京东", "淘宝/天猫", "拼多多"]


# =============================================================================
# 二、产品指纹库 — 每个产品的识别关键词和竞品品牌列表
# =============================================================================

# 每个产品的「正面指纹」
# - brand_keywords: 品牌层级关键词（出现在 SKU 或 content 中表示品牌相关）
# - model_keywords: 型号层级关键词（出现在 content 中表示型号相关）
# - sku_color_keywords: 该产品的特征色名称（各产品独有的颜色命名是强正面信号）
# - brand_id: 品牌唯一标识符
PRODUCT_FINGERPRINTS = {
    "iPhone 17 Pro": {
        "brand_keywords": ["iphone", "苹果", "apple"],
        "model_keywords": ["17 pro", "17pro", "iphone17", "iphone 17", "a19"],
        "sku_color_keywords": ["星宇橙", "薰衣草紫", "青雾蓝", "鼠尾草绿", "深青",
                               "群青"],
        "brand_id":       "apple",
    },
    "Huawei P70": {
        "brand_keywords": ["华为", "huawei", "鸿蒙"],
        "model_keywords": ["p70", "pura70", "pura 70", "p 70", "麒麟"],
        "sku_color_keywords": ["冰晶蓝", "雪域白", "羽砂黑", "北斗", "卫星消息",
                               "星河金"],
        "brand_id":       "huawei",
    },
    "Xiaomi 15 Pro": {
        "brand_keywords": ["小米", "xiaomi", "miui", "hyper os", "澎湃"],
        "model_keywords": ["15 pro", "15pro", "小米15"],
        "sku_color_keywords": ["岩石灰", "云杉绿"],
        "brand_id":       "xiaomi",
    },
    "VIVO X300 Pro": {
        "brand_keywords": ["vivo"],
        "model_keywords": ["x300", "x 300"],
        "sku_color_keywords": ["旷野棕", "简单白", "纯粹黑", "自在蓝",
                               "摄影师套装"],
        "brand_id":       "vivo",
    },
    "OPPO Find X9 Pro": {
        "brand_keywords": ["oppo"],
        "model_keywords": ["find x9", "findx9", "x9 pro", "x9pro"],
        "sku_color_keywords": ["绒砂钛", "追光红", "绒光钛", "霜白",
                               "雾黑"],
        "brand_id":       "oppo",
    },
    "OnePlus 14": {
        "brand_keywords": ["一加", "oneplus", "1+"],
        "model_keywords": ["一加14", "oneplus 14", "oneplus14"],
        "sku_color_keywords": ["原色沙丘", "雾光紫", "绝对黑"],
        "brand_id":       "oneplus",
    },
}

# 所有品牌标识符和对应关键词（用于品牌冲突检测）
ALL_BRANDS = {
    "apple":    ["iphone", "苹果", "apple", "ios"],
    "huawei":   ["华为", "huawei", "鸿蒙", "harmonyos"],
    "xiaomi":   ["小米", "xiaomi", "红米", "redmi"],
    "vivo":     ["vivo"],
    "samsung":  ["三星", "samsung", "galaxy"],
    "oppo":     ["oppo"],
    "oneplus":  ["一加", "oneplus", "1+"],
    "honor":    ["荣耀", "honor"],
    "realme":   ["realme", "真我"],
    "iqoo":     ["iqoo"],
    "meizu":    ["魅族", "meizu"],
    "motorola": ["摩托罗拉", "motorola", "moto"],
    "google":   ["pixel", "谷歌"],
    "sony":     ["索尼", "sony", "xperia"],
    "nokia":    ["诺基亚", "nokia"],
    "zte":      ["中兴", "zte"],
    "nubia":    ["努比亚", "nubia"],
    "lenovo":   ["联想", "lenovo"],
}

# 正常SKU格式验证模式 — 用于判断SKU是否为正常的"颜色+配置"格式
# 如果SKU匹配这些模式，说明至少结构正常（即使没有品牌关键词）
NORMAL_SKU_PATTERNS = [
    r"已购",                           # 京东格式: "已购 颜色 容量"
    r"机身颜色",                       # 拼多多格式: "机身颜色:xxx; 存储容量:xxx"
    r"存储容量",
    r"套餐类型",
    r"网络类型",
    r"\d+GB",                          # 容量关键词
    r"\d+TB",
    r"全网通",
    r"官方标配",
]

# 通用手机评论词汇（这些词不具有品牌区分力，出现不代表混入）
GENERIC_PHONE_TERMS = [
    "手机", "充电", "电池", "屏幕", "拍照", "相机", "系统", "处理器", "芯片",
    "内存", "存储", "信号", "wifi", "5g", "4g", "蓝牙", "指纹", "面部识别",
    "快充", "续航", "发热", "散热", "游戏", "流畅", "卡顿", "像素", "分辨率",
    "刷新率", "护眼", "重量", "手感", "外观", "颜值", "做工", "质感", "配件",
    "保护壳", "贴膜", "耳机", "充电器", "数据线", "官方标配", "全网通",
]


# =============================================================================
# 三、工具函数
# =============================================================================

def normalize_product_name(filename: str) -> str:
    """根据文件名推断并返回标准化的产品名称。"""
    fn_lower = filename.lower().replace(" ", "_").replace("-", "_")
    for keyword, standard_name in PRODUCT_NAME_MAP.items():
        if keyword.lower().replace(" ", "_").replace("-", "_") in fn_lower:
            return standard_name
    return filename


def text_contains_any(text: str, keywords: list[str], case_insensitive: bool = True) -> list[str]:
    """
    检查文本中是否包含关键词列表中的任何一个。
    返回匹配到的关键词列表。
    """
    if not text:
        return []
    check_text = text.lower() if case_insensitive else text
    matched = []
    for kw in keywords:
        check_kw = kw.lower() if case_insensitive else kw
        if check_kw in check_text:
            matched.append(kw)
    return matched


def is_normal_sku_format(sku: str) -> bool:
    """
    判断 SKU 是否为正常的电商平台格式（颜色+容量+套餐）。
    正常格式的 SKU 不含品牌名是完全合理的，不应因此扣分。
    """
    if not sku:
        return False
    for pattern in NORMAL_SKU_PATTERNS:
        if re.search(pattern, sku, re.IGNORECASE):
            return True
    return False


def detect_brands_in_text(text: str) -> set[str]:
    """
    检测文本中出现的所有品牌标识符。
    返回品牌ID的集合，如 {'apple', 'samsung'}。
    """
    if not text:
        return set()
    text_lower = text.lower()
    found = set()
    for brand_id, keywords in ALL_BRANDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                found.add(brand_id)
                break
    return found


# =============================================================================
# 四、核心验证类
# =============================================================================

class ReviewRelevanceResult:
    """单条评论的相关性验证结果。"""

    def __init__(self, review: dict, target_product: str):
        self.review = review
        self.target_product = target_product
        self.review_id = review.get("id", "")

        # 各项检测结果
        self.sku_brand_match = False          # SKU 中是否含目标品牌关键词
        self.sku_model_match = False          # SKU 中是否含目标型号关键词
        self.content_brand_match = False      # 内容中是否提到目标品牌
        self.content_model_match = False      # 内容中是否提到目标型号
        self.has_brand_conflict = False       # 是否存在品牌冲突
        self.conflicting_brands: set = set()  # 冲突的品牌列表
        self.sku_is_empty = False             # SKU 是否为空
        self.content_is_empty = False         # 内容是否为空

        # 综合置信度（0.0 - 1.0）
        self.confidence_score: float = 0.0

        # 疑似标签
        self.suspect_reasons: list[str] = []

    @property
    def is_suspect(self) -> bool:
        """是否为可疑评论（置信度低于阈值）。"""
        return self.confidence_score < 0.5

    @property
    def is_likely_irrelevant(self) -> bool:
        """是否大概率无关（置信度极低或有强冲突证据）。"""
        return self.confidence_score < 0.3 or self.has_brand_conflict


class FileRelevanceProfile:
    """单个数据文件的相关性验证结果。"""

    def __init__(self, filepath: str, platform: str, target_product: str):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.platform = platform
        self.target_product = target_product

        # 加载数据
        with open(filepath, "r", encoding="utf-8") as f:
            self.data: list[dict] = json.load(f)

        self.total_reviews = len(self.data)
        self.results: list[ReviewRelevanceResult] = []

        # product_name 一致性分析
        self.unique_product_names: Counter = Counter()

        # 聚合统计
        self.suspect_count = 0
        self.likely_irrelevant_count = 0
        self.brand_conflict_count = 0
        self.avg_confidence = 0.0

        # 执行验证
        self._validate_all()

    def _validate_all(self):
        """对文件中每条评论执行完整的相关性校验。"""
        fingerprint = PRODUCT_FINGERPRINTS.get(self.target_product)
        if not fingerprint:
            # 未知产品，无法校验
            return

        target_brand_id = fingerprint["brand_id"]
        scores = []

        for review in self.data:
            result = self._validate_one_review(review, fingerprint, target_brand_id)
            self.results.append(result)
            scores.append(result.confidence_score)

            # 统计 product_name
            pn = review.get("product_name", "")
            self.unique_product_names[pn] += 1

            # 聚合
            if result.is_suspect:
                self.suspect_count += 1
            if result.is_likely_irrelevant:
                self.likely_irrelevant_count += 1
            if result.has_brand_conflict:
                self.brand_conflict_count += 1

        self.avg_confidence = statistics.mean(scores) if scores else 0.0

    def _validate_one_review(
        self, review: dict, fingerprint: dict, target_brand_id: str
    ) -> ReviewRelevanceResult:
        """
        对单条评论执行多维度验证，返回结果。

        评分设计理念：
        - 基础分 0.7（"先信任"原则：来自目标文件的评论大概率是正确的）
        - 正面信号（品牌/型号/特征色匹配）→ 加分
        - 强负面信号（SKU 中出现其他品牌 or SKU 结构完全异常）→ 大幅扣分
        - SKU 只有"颜色+容量"不含品牌名 → 中性（这是平台的正常格式）
        """
        result = ReviewRelevanceResult(review, self.target_product)

        content = review.get("content", "") or ""
        sku = review.get("model_sku", "") or ""

        # --- 基础状态 ---
        result.content_is_empty = not content.strip()
        result.sku_is_empty = not sku.strip()

        # --- 维度1：SKU 品牌关键词匹配 ---
        sku_brand_matches = text_contains_any(sku, fingerprint["brand_keywords"])
        result.sku_brand_match = bool(sku_brand_matches)

        # --- 维度2：SKU 型号关键词匹配 ---
        sku_model_matches = text_contains_any(sku, fingerprint["model_keywords"])
        result.sku_model_match = bool(sku_model_matches)

        # --- 维度3：评论内容品牌匹配 ---
        content_brand_matches = text_contains_any(content, fingerprint["brand_keywords"])
        result.content_brand_match = bool(content_brand_matches)

        # --- 维度4：评论内容型号匹配 ---
        content_model_matches = text_contains_any(content, fingerprint["model_keywords"])
        result.content_model_match = bool(content_model_matches)

        # --- 维度5：品牌冲突检测 ---
        # 只在 SKU 中检测品牌冲突（评论内容中提到竞品是正常的对比行为）
        sku_brands = detect_brands_in_text(sku)
        sku_other_brands = sku_brands - {target_brand_id}
        if sku_other_brands:
            result.has_brand_conflict = True
            result.conflicting_brands = sku_other_brands
            result.suspect_reasons.append(
                f"SKU中出现非目标品牌: {', '.join(sku_other_brands)}"
            )

        # --- 维度6：SKU 特征色匹配 ---
        sku_color_keywords = fingerprint.get("sku_color_keywords", [])
        sku_color_matches = text_contains_any(sku, sku_color_keywords)

        # --- 维度7：SKU 结构正常性检测 ---
        sku_is_normal_format = is_normal_sku_format(sku)

        # ============================================================
        # 综合置信度计算
        # ============================================================
        # 基础分：0.7（"先信任"原则）
        score = 0.70

        # ----- 正面信号（累计加分） -----

        # SKU 中直接包含品牌名（如京东"已购 vivo"）→ 强正面
        if result.sku_brand_match:
            score += 0.15

        # SKU 中包含产品特征色（如 iPhone 的"星宇橙"）→ 强正面
        if sku_color_matches:
            score += 0.15

        # 评论内容中提到了目标型号（如"17 pro"）→ 中等正面
        if result.content_model_match:
            score += 0.08

        # 评论内容中提到了目标品牌（如"苹果"）→ 弱正面
        if result.content_brand_match:
            score += 0.04

        # ----- 负面信号（扣分） -----

        # SKU 品牌冲突 → 极强负信号，几乎一定是混入
        if result.has_brand_conflict:
            score -= 0.65

        # SKU 结构完全异常（不是正常的"颜色+容量"格式，也不含品牌名）
        # 这可能是手机壳、配件等非手机商品的评论混入
        if not result.sku_is_empty and not sku_is_normal_format and not result.sku_brand_match:
            score -= 0.40
            result.suspect_reasons.append(
                f"SKU结构异常，非标准手机SKU格式 (sku={sku[:60]})"
            )

        # 内容为空 → 轻微扣分（无法做内容分析，但不一定是混入）
        if result.content_is_empty:
            score -= 0.03

        # 限制在 [0, 1] 范围
        result.confidence_score = max(0.0, min(1.0, score))

        return result

    # --- 统计属性 ---

    @property
    def suspect_rate(self) -> float:
        """可疑评论比例。"""
        return self.suspect_count / self.total_reviews if self.total_reviews else 0

    @property
    def likely_irrelevant_rate(self) -> float:
        """大概率无关评论比例。"""
        return self.likely_irrelevant_count / self.total_reviews if self.total_reviews else 0

    @property
    def product_name_count(self) -> int:
        """文件内不同 product_name 值的个数。"""
        return len(self.unique_product_names)

    @property
    def top_suspect_reviews(self) -> list[ReviewRelevanceResult]:
        """按置信度排序，返回置信度最低的评论（最可疑的）。"""
        return sorted(self.results, key=lambda r: r.confidence_score)[:20]

    def get_brand_conflict_details(self) -> dict[str, int]:
        """返回品牌冲突统计。"""
        conflicts = Counter()
        for r in self.results:
            for brand in r.conflicting_brands:
                conflicts[brand] += 1
        return dict(conflicts.most_common())


class DataRelevanceValidator:
    """整个数据集的相关性验证器。"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.file_profiles: list[FileRelevanceProfile] = []
        self._scan_and_validate()

    def _scan_and_validate(self):
        """扫描数据目录，加载并验证所有 JSON 文件。"""
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

                print(f"  验证 [{platform_name}] {filename} -> {product_name}")
                profile = FileRelevanceProfile(filepath, platform_name, product_name)
                self.file_profiles.append(profile)

    # --- 聚合查询 ---

    def get_profiles_by_platform(self, platform: str) -> list[FileRelevanceProfile]:
        return [fp for fp in self.file_profiles if fp.platform == platform]

    def get_profiles_by_product(self, product: str) -> list[FileRelevanceProfile]:
        return [fp for fp in self.file_profiles if fp.target_product == product]

    @property
    def total_reviews(self) -> int:
        return sum(fp.total_reviews for fp in self.file_profiles)

    @property
    def total_suspects(self) -> int:
        return sum(fp.suspect_count for fp in self.file_profiles)

    @property
    def total_likely_irrelevant(self) -> int:
        return sum(fp.likely_irrelevant_count for fp in self.file_profiles)

    @property
    def total_brand_conflicts(self) -> int:
        return sum(fp.brand_conflict_count for fp in self.file_profiles)

    @property
    def overall_avg_confidence(self) -> float:
        all_scores = []
        for fp in self.file_profiles:
            for r in fp.results:
                all_scores.append(r.confidence_score)
        return statistics.mean(all_scores) if all_scores else 0


# =============================================================================
# 五、报告生成
# =============================================================================

def generate_validation_report(validator: DataRelevanceValidator) -> str:
    """生成完整的数据有效性验证 Markdown 报告。"""
    lines = []

    def ln(text=""):
        lines.append(text)

    # ---------------------------
    # 标题
    # ---------------------------
    ln("# 🔍 跨平台电商评论数据有效性验证报告")
    ln()
    ln(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    ln(f"> 数据目录：`{validator.data_dir}`")
    ln()

    # ---------------------------
    # 1. 验证总览
    # ---------------------------
    ln("## 一、验证总览")
    ln()
    ln("| 指标 | 值 |")
    ln("|:---|:---|")
    ln(f"| 扫描文件数 | {len(validator.file_profiles)} |")
    ln(f"| **总评论数** | **{validator.total_reviews:,}** |")
    ln(f"| 高置信度评论数（≥0.5） | {validator.total_reviews - validator.total_suspects:,} |")
    ln(f"| ⚠️ 可疑评论数（<0.5） | {validator.total_suspects:,} |")
    ln(f"| 🚨 大概率无关评论数（<0.3 或有品牌冲突） | {validator.total_likely_irrelevant:,} |")
    ln(f"| 品牌冲突评论数 | {validator.total_brand_conflicts:,} |")
    ln(f"| 整体平均置信度 | {validator.overall_avg_confidence:.3f} |")
    ln()

    overall_suspect_rate = validator.total_suspects / validator.total_reviews if validator.total_reviews else 0
    overall_irrelevant_rate = validator.total_likely_irrelevant / validator.total_reviews if validator.total_reviews else 0

    if overall_suspect_rate < 0.02:
        ln("> ✅ **数据有效性良好**：可疑评论比例仅 {:.1%}，大部分评论可确认属于目标产品。".format(overall_suspect_rate))
    elif overall_suspect_rate < 0.10:
        ln("> ⚠️ **数据存在一定噪声**：可疑评论比例 {:.1%}，建议在训练前做针对性清洗。".format(overall_suspect_rate))
    else:
        ln("> 🚨 **数据污染较严重**：可疑评论比例 {:.1%}，强烈建议清洗后再投入训练。".format(overall_suspect_rate))
    ln()

    # ---------------------------
    # 2. 分文件有效性九宫格
    # ---------------------------
    ln("## 二、数据有效性九宫格（平台 × 产品）")
    ln()

    # 2.1 平均置信度九宫格
    ln("### 2.1 平均置信度")
    ln()
    ln("> 置信度范围 0~1，越高表示该组数据越可能都属于目标产品。")
    ln()

    header = "| 产品 \\\\ 平台 | " + " | ".join(ALL_PLATFORMS) + " |"
    sep = "|:---|" + "|".join(["---:"] * len(ALL_PLATFORMS)) + "|"
    ln(header)
    ln(sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            fps = [fp for fp in validator.file_profiles
                   if fp.platform == platform and fp.target_product == product]
            if fps:
                # 合并多个文件的得分
                all_scores = []
                for fp in fps:
                    all_scores.extend([r.confidence_score for r in fp.results])
                avg = statistics.mean(all_scores) if all_scores else 0
                # 颜色标注
                if avg >= 0.8:
                    row += f" ✅ {avg:.3f} |"
                elif avg >= 0.5:
                    row += f" ⚠️ {avg:.3f} |"
                else:
                    row += f" 🚨 {avg:.3f} |"
            else:
                row += " - |"
        ln(row)
    ln()

    # 2.2 可疑评论数九宫格
    ln("### 2.2 可疑评论数（置信度 < 0.5）")
    ln()
    header2 = "| 产品 \\\\ 平台 | " + " | ".join([f"{p} (数量/比例)" for p in ALL_PLATFORMS]) + " |"
    ln(header2)
    ln(sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            fps = [fp for fp in validator.file_profiles
                   if fp.platform == platform and fp.target_product == product]
            if fps:
                total = sum(fp.total_reviews for fp in fps)
                suspects = sum(fp.suspect_count for fp in fps)
                rate = suspects / total if total else 0
                row += f" {suspects} / {rate:.1%} |"
            else:
                row += " - |"
        ln(row)
    ln()

    # 2.3 品牌冲突九宫格
    ln("### 2.3 品牌冲突评论数")
    ln()
    ln("> 品牌冲突：评论的 SKU 字段中出现了与目标产品不同品牌的关键词。这是最强的混入信号。")
    ln()
    header3 = "| 产品 \\\\ 平台 | " + " | ".join(ALL_PLATFORMS) + " |"
    ln(header3)
    ln(sep)

    for product in ALL_PRODUCTS:
        row = f"| {product} |"
        for platform in ALL_PLATFORMS:
            fps = [fp for fp in validator.file_profiles
                   if fp.platform == platform and fp.target_product == product]
            if fps:
                conflicts = sum(fp.brand_conflict_count for fp in fps)
                total = sum(fp.total_reviews for fp in fps)
                rate = conflicts / total if total else 0
                if conflicts == 0:
                    row += " ✅ 0 |"
                else:
                    row += f" 🚨 {conflicts} ({rate:.1%}) |"
            else:
                row += " - |"
        ln(row)
    ln()

    # ---------------------------
    # 3. product_name 一致性分析
    # ---------------------------
    ln("## 三、product_name 字段一致性分析")
    ln()
    ln("> 同一数据文件中 `product_name` 字段应该保持一致。如果出现多个不同值，")
    ln("> 可能是爬虫从多个商品页面混合了数据，或平台搜索推荐污染了结果。")
    ln()
    ln("| 平台 | 文件 | 目标产品 | product_name 种类数 | 状态 |")
    ln("|:---|:---|:---|---:|:---|")

    has_inconsistency = False
    for fp in validator.file_profiles:
        pn_count = fp.product_name_count
        if pn_count <= 1:
            status = "✅ 一致"
        elif pn_count <= 5:
            status = "⚠️ 存在多个值"
            has_inconsistency = True
        else:
            status = f"🚨 高度分散（{pn_count}个值）"
            has_inconsistency = True
        ln(f"| {fp.platform} | `{fp.filename}` | {fp.target_product} | {pn_count} | {status} |")
    ln()

    # 详细展示不一致的文件
    if has_inconsistency:
        ln("### 3.1 product_name 不一致文件详情")
        ln()
        for fp in validator.file_profiles:
            if fp.product_name_count > 1:
                ln(f"**{fp.platform} - `{fp.filename}`**（目标：{fp.target_product}）")
                ln()
                ln("| product_name 值 | 评论数 | 占比 |")
                ln("|:---|---:|---:|")
                for name, count in fp.unique_product_names.most_common():
                    rate = count / fp.total_reviews if fp.total_reviews else 0
                    display_name = name if len(name) <= 40 else name[:37] + "..."
                    ln(f"| {display_name} | {count} | {rate:.1%} |")
                ln()

    # ---------------------------
    # 4. 品牌冲突详情
    # ---------------------------
    ln("## 四、品牌冲突详情分析")
    ln()
    ln("> 以下统计每个文件中被检测到的冲突品牌分布。冲突品牌出现在 SKU 中意味着")
    ln("> 该评论很可能是其他品牌产品的评论，而非目标产品。")
    ln()

    has_conflict = False
    for fp in validator.file_profiles:
        conflicts = fp.get_brand_conflict_details()
        if conflicts:
            has_conflict = True
            ln(f"### {fp.platform} - `{fp.filename}`（目标：{fp.target_product}）")
            ln()
            ln("| 冲突品牌 | 评论数 |")
            ln("|:---|---:|")
            for brand, count in conflicts.items():
                brand_display = {
                    "apple": "Apple/苹果", "huawei": "华为", "xiaomi": "小米/红米",
                    "vivo": "vivo", "samsung": "三星", "oppo": "OPPO",
                    "oneplus": "一加", "honor": "荣耀", "realme": "真我/realme",
                    "iqoo": "iQOO", "meizu": "魅族", "motorola": "摩托罗拉",
                    "google": "Google/Pixel", "sony": "索尼", "nokia": "诺基亚",
                    "zte": "中兴", "nubia": "努比亚", "lenovo": "联想",
                }.get(brand, brand)
                ln(f"| {brand_display} | {count} |")
            ln()

    if not has_conflict:
        ln("✅ **未检测到品牌冲突** — 所有文件的 SKU 字段均只包含目标产品品牌的关键词。")
        ln()

    # ---------------------------
    # 5. 置信度分布分析
    # ---------------------------
    ln("## 五、置信度分布分析")
    ln()
    ln("> 统计各置信度区间的评论数量分布，帮助判断合适的清洗阈值。")
    ln()

    # 按平台统计
    ln("### 5.1 各平台置信度分布")
    ln()
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
    bin_labels = ["[0.0, 0.2)", "[0.2, 0.4)", "[0.4, 0.6)", "[0.6, 0.8)", "[0.8, 1.0]"]

    header_conf = "| 平台 | " + " | ".join(bin_labels) + " | 总计 |"
    sep_conf = "|:---|" + "|".join(["---:"] * len(bin_labels)) + "|---:|"
    ln(header_conf)
    ln(sep_conf)

    for platform in ALL_PLATFORMS:
        fps = validator.get_profiles_by_platform(platform)
        if not fps:
            continue
        bin_counts = [0] * len(bins)
        total = 0
        for fp in fps:
            for r in fp.results:
                total += 1
                for idx, (lo, hi) in enumerate(bins):
                    if lo <= r.confidence_score < hi:
                        bin_counts[idx] += 1
                        break
        row = f"| {platform} |"
        for cnt in bin_counts:
            row += f" {cnt:,} |"
        row += f" {total:,} |"
        ln(row)
    ln()

    # 按产品统计
    ln("### 5.2 各产品置信度分布")
    ln()
    ln(header_conf)
    ln(sep_conf)

    for product in ALL_PRODUCTS:
        fps = validator.get_profiles_by_product(product)
        if not fps:
            continue
        bin_counts = [0] * len(bins)
        total = 0
        for fp in fps:
            for r in fp.results:
                total += 1
                for idx, (lo, hi) in enumerate(bins):
                    if lo <= r.confidence_score < hi:
                        bin_counts[idx] += 1
                        break
        row = f"| {product} |"
        for cnt in bin_counts:
            row += f" {cnt:,} |"
        row += f" {total:,} |"
        ln(row)
    ln()

    # ---------------------------
    # 6. 最可疑评论样例
    # ---------------------------
    ln("## 六、最可疑评论样例")
    ln()
    ln("> 以下列出各文件中置信度最低的评论样例，帮助人工核实验证逻辑的准确性。")
    ln()

    for fp in validator.file_profiles:
        top_suspects = fp.top_suspect_reviews[:5]
        if not top_suspects or top_suspects[0].confidence_score >= 0.5:
            continue  # 跳过没有可疑评论的文件

        ln(f"### {fp.platform} - {fp.target_product}（`{fp.filename}`）")
        ln()
        ln("| # | 置信度 | SKU（截取） | 评论内容（截取） | 疑似原因 |")
        ln("|---:|---:|:---|:---|:---|")

        for i, r in enumerate(top_suspects, 1):
            if r.confidence_score >= 0.5:
                break
            sku = r.review.get("model_sku", "")
            sku_display = sku[:40] + "..." if len(sku) > 40 else sku
            content = r.review.get("content", "")
            content_display = content[:50] + "..." if len(content) > 50 else content
            # 转义管道符
            sku_display = sku_display.replace("|", "\\|")
            content_display = content_display.replace("|", "\\|")
            reasons = "; ".join(r.suspect_reasons) if r.suspect_reasons else "综合得分低"
            reasons = reasons.replace("|", "\\|")
            ln(f"| {i} | {r.confidence_score:.2f} | {sku_display} | {content_display} | {reasons} |")
        ln()

    # ---------------------------
    # 7. 清洗建议
    # ---------------------------
    ln("## 七、数据清洗建议")
    ln()

    ln("### 7.1 清洗策略推荐")
    ln()

    # 根据数据分析结果给出建议
    if validator.total_brand_conflicts > 0:
        ln(f"1. **优先清除品牌冲突评论**：共 {validator.total_brand_conflicts} 条评论的 "
           f"SKU 字段中出现了与目标产品不同的品牌关键词，这些几乎可以确定是混入的非目标产品评论，"
           f"建议直接从数据集中移除。")
    else:
        ln("1. **品牌冲突**：未检测到 SKU 级别的品牌冲突，数据源头较纯净。")

    if validator.total_suspects > 0:
        ln(f"2. **可疑评论处理**：共 {validator.total_suspects:,} 条评论置信度低于 0.5，"
           f"可考虑设置阈值过滤。推荐的清洗阈值为 **0.45**（平衡召回与精度）。")
    else:
        ln("2. **可疑评论**：未检测到置信度低于 0.5 的评论。")

    # 检查拼多多 product_name 问题
    pdd_profiles = validator.get_profiles_by_platform("拼多多")
    pdd_multi_names = [fp for fp in pdd_profiles if fp.product_name_count > 1]
    if pdd_multi_names:
        ln(f"3. **拼多多 product_name 归一化**：拼多多 {len(pdd_multi_names)} 个文件的 "
           f"`product_name` 字段包含商品ID格式值（如\"商品904664626870\"），"
           f"这是由于爬虫从多个商品链接采集导致的。这不代表数据混入——同一型号在不同店铺有不同商品ID。"
           f"但建议在预处理阶段统一映射为标准产品名称。")

    ln()

    ln("### 7.2 各文件清洗优先级")
    ln()
    ln("| 优先级 | 平台 | 文件 | 产品 | 可疑率 | 品牌冲突数 | 建议操作 |")
    ln("|---:|:---|:---|:---|---:|---:|:---|")

    # 按可疑率排序
    sorted_profiles = sorted(
        validator.file_profiles,
        key=lambda fp: fp.suspect_rate,
        reverse=True
    )

    for i, fp in enumerate(sorted_profiles, 1):
        if fp.suspect_rate == 0 and fp.brand_conflict_count == 0:
            action = "✅ 无需清洗"
        elif fp.brand_conflict_count > 0:
            action = "🚨 需清除品牌冲突项"
        elif fp.suspect_rate > 0.05:
            action = "⚠️ 建议人工审查"
        else:
            action = "🔸 少量可疑，可忽略"
        ln(f"| {i} | {fp.platform} | `{fp.filename}` | {fp.target_product} | "
           f"{fp.suspect_rate:.1%} | {fp.brand_conflict_count} | {action} |")
    ln()

    ln("---")
    ln("*本报告由 `data_relevance_validator.py` 自动生成，如需更新请重新运行脚本。*")

    return "\n".join(lines)


# =============================================================================
# 六、可疑评论导出
# =============================================================================

def export_suspect_reviews(validator: DataRelevanceValidator, output_dir: str):
    """将可疑评论按文件导出为 JSON，方便人工审查。"""
    os.makedirs(output_dir, exist_ok=True)
    total_exported = 0

    for fp in validator.file_profiles:
        suspects = [r for r in fp.results if r.is_suspect]
        if not suspects:
            continue

        output_data = []
        for r in suspects:
            output_data.append({
                "id": r.review.get("id", ""),
                "confidence_score": round(r.confidence_score, 3),
                "suspect_reasons": r.suspect_reasons,
                "has_brand_conflict": r.has_brand_conflict,
                "conflicting_brands": list(r.conflicting_brands),
                "review": r.review,
            })

        # 输出文件名
        base = os.path.splitext(fp.filename)[0]
        output_file = os.path.join(output_dir, f"suspects_{base}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"  📄 导出 {len(output_data)} 条可疑评论 -> {output_file}")
        total_exported += len(output_data)

    print(f"\n  总共导出 {total_exported} 条可疑评论到 {output_dir}/")


# =============================================================================
# 七、主入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="跨平台电商评论数据有效性验证工具",
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
        default="data_relevance_report.md",
        help="输出报告的文件名（默认 data_relevance_report.md）",
    )
    parser.add_argument(
        "--export-suspects",
        action="store_true",
        help="导出可疑评论明细到 suspects/ 目录",
    )
    parser.add_argument(
        "--suspects-dir",
        type=str,
        default="suspects",
        help="可疑评论导出目录（默认 suspects/）",
    )
    parser.add_argument(
        "--no-file",
        action="store_true",
        help="仅输出到控制台，不生成文件",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  跨平台电商评论数据有效性验证")
    print("=" * 60)
    print(f"  数据目录: {args.data_dir}")
    print()

    # 加载并验证
    validator = DataRelevanceValidator(args.data_dir)

    print()
    print(f"  验证完成: 共扫描 {len(validator.file_profiles)} 个文件, "
          f"{validator.total_reviews:,} 条评论")
    print(f"  可疑评论: {validator.total_suspects:,} 条 "
          f"({validator.total_suspects/validator.total_reviews:.1%})")
    print(f"  品牌冲突: {validator.total_brand_conflicts:,} 条")
    print(f"  整体置信度: {validator.overall_avg_confidence:.3f}")
    print()

    # 生成报告
    report = generate_validation_report(validator)

    # 输出报告
    if not args.no_file:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  ✅ 报告已保存: {output_path}")

    # 导出可疑评论
    if args.export_suspects:
        suspects_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.suspects_dir)
        export_suspect_reviews(validator, suspects_path)

    print()
    print("完成！")


if __name__ == "__main__":
    main()
