# -*- coding: utf-8 -*-
"""
清洗后数据集分析报告生成器（中文版）
输入: data/cleaned/all_reviews.json
输出: data/cleaned/README.md
"""

import json
import os
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime

CLEANED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cleaned", "all_reviews.json")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cleaned", "README.md")

PLATFORM_LABELS = {"jd": "京东", "taobao": "淘宝/天猫", "pdd": "拼多多"}
PLATFORM_ORDER = ["jd", "taobao", "pdd"]


def count_sentences(text):
    if not text:
        return 0
    sents = re.split(r'[。！？；\n]+|[.!?;]\s+', text.strip())
    sents = [s.strip() for s in sents if s.strip()]
    return max(len(sents), 1) if text.strip() else 0


def main():
    with open(CLEANED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    def ln(text=""):
        lines.append(text)

    products = sorted(set(item["product"] for item in data))
    platforms = PLATFORM_ORDER

    grid = defaultdict(lambda: defaultdict(int))
    for item in data:
        grid[item["product"]][item["platform"]] += 1

    total = len(data)
    total_by_platform = {p: sum(grid[pr][p] for pr in products) for p in platforms}
    total_by_product = {pr: sum(grid[pr][p] for p in platforms) for pr in products}

    lengths = [len(item["content"]) for item in data]
    sentences = [count_sentences(item["content"]) for item in data]

    platform_lengths = defaultdict(list)
    platform_sents = defaultdict(list)
    for item in data:
        platform_lengths[item["platform"]].append(len(item["content"]))
        platform_sents[item["platform"]].append(count_sentences(item["content"]))

    dates_by_platform = defaultdict(list)
    for item in data:
        d = item.get("date", "")
        if re.match(r"\d{4}-\d{2}-\d{2}$", d):
            dates_by_platform[item["platform"]].append(d)

    # ================================================================
    # Markdown 报告
    # ================================================================

    ln("# 跨平台电商评论数据集")
    ln()
    ln(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    ln()

    # --- 1. 总览 ---
    ln("## 一、数据集总览")
    ln()
    ln("| 指标 | 值 |")
    ln("|:---|:---|")
    ln(f"| **评论总量** | **{total:,}** 条 |")
    ln(f"| 覆盖产品 | {len(products)} 款智能手机 |")
    ln(f"| 覆盖平台 | {len(platforms)} 个（京东、淘宝/天猫、拼多多） |")
    ln(f"| 每条记录字段数 | 6 个（`id`, `platform`, `product`, `content`, `date`, `sku`） |")
    ln(f"| 平均评论长度 | {statistics.mean(lengths):.0f} 字符（中位数 {statistics.median(lengths):.0f}） |")
    ln(f"| 平均句子数 | {statistics.mean(sentences):.1f} 句（中位数 {statistics.median(sentences):.0f}） |")
    ln()

    # --- 2. 数据分布九宫格 ---
    ln("## 二、数据分布（产品 × 平台）")
    ln()
    header = "| 产品 | " + " | ".join(PLATFORM_LABELS[p] for p in platforms) + " | 合计 |"
    sep = "|:---|" + "|".join(["---:"] * len(platforms)) + "|---:|"
    ln(header)
    ln(sep)

    for pr in products:
        row = f"| {pr} |"
        for p in platforms:
            row += f" {grid[pr][p]:,} |"
        row += f" {total_by_product[pr]:,} |"
        ln(row)

    totals_row = "| **合计** |"
    for p in platforms:
        totals_row += f" **{total_by_platform[p]:,}** |"
    totals_row += f" **{total:,}** |"
    ln(totals_row)
    ln()

    ln("**各平台占比：**")
    for p in platforms:
        pct = total_by_platform[p] / total * 100
        ln(f"- {PLATFORM_LABELS[p]}：{total_by_platform[p]:,} 条（{pct:.1f}%）")
    ln()

    # --- 3. 文本统计 ---
    ln("## 三、文本统计")
    ln()
    ln("| 平台 | 数量 | 平均长度 | 中位长度 | 平均句数 | 中位句数 | 时间跨度 |")
    ln("|:---|---:|---:|---:|---:|---:|:---|")

    for p in platforms:
        pl = platform_lengths[p]
        ps = platform_sents[p]
        dates = sorted(dates_by_platform[p])
        dr = f"{dates[0]} ~ {dates[-1]}" if dates else "N/A"
        ln(f"| {PLATFORM_LABELS[p]} | {len(pl):,} | {statistics.mean(pl):.0f} | {statistics.median(pl):.0f} | {statistics.mean(ps):.1f} | {statistics.median(ps):.0f} | {dr} |")
    ln()

    ln("**评论长度分布：**")
    ln()
    brackets = [(0, 10), (10, 30), (30, 50), (50, 100), (100, 200), (200, 500), (500, float('inf'))]
    bracket_labels = ["≤10", "11-30", "31-50", "51-100", "101-200", "201-500", ">500"]
    ln("| 长度(字符) | " + " | ".join(bracket_labels) + " |")
    ln("|:---|" + "|".join(["---:"] * len(brackets)) + "|")

    row = "| 数量 |"
    for lo, hi in brackets:
        cnt = sum(1 for l in lengths if lo < l <= hi) if lo > 0 else sum(1 for l in lengths if l <= hi)
        row += f" {cnt:,} |"
    ln(row)

    row = "| 占比 |"
    for lo, hi in brackets:
        cnt = sum(1 for l in lengths if lo < l <= hi) if lo > 0 else sum(1 for l in lengths if l <= hi)
        row += f" {cnt/total*100:.1f}% |"
    ln(row)
    ln()

    # --- 4. 预处理流程 ---
    ln("## 四、预处理流程")
    ln()
    ln("原始评论数据经过以下预处理步骤：")
    ln()
    ln("1. **删除系统默认好评**：移除各平台的默认评价模板，")
    ln("   包括京东的「此用户未填写评价内容」、拼多多的「该用户觉得商品很好，给出了5星好评」等。")
    ln("2. **删除单字评论**：移除有效字符 ≤1 的超短评论。")
    ln("3. **追评拼接**：将追加评论（`append_content`）以 `[追评]` 分隔符拼接到原始评论末尾。")
    ln("4. **按评论 ID 去重**：移除具有相同平台评论 ID 的重复条目。")
    ln("   拼多多平台以商品（SPU）为单位聚合评论，不同店铺展示同一评论池，因此按 ID 去重可自然消除跨店铺重复。")
    ln("5. **字段标准化**：统一平台名称（`jd`/`taobao`/`pdd`）、产品名称（10 个标准名）、")
    ln("   日期格式（`YYYY-MM-DD`）及 SKU 描述。移除实验不需要的字段（`votes`、`images`、`reply`、`score`）。")
    ln()

    # --- 5. 数据结构 ---
    ln("## 五、数据结构")
    ln()
    ln("```json")
    ln("{")
    ln('  "id": "jd_103902930162031324",')
    ln('  "platform": "jd",')
    ln('  "product": "iPhone_17_Pro",')
    ln('  "content": "手机非常好用，拍照清晰...",')
    ln('  "date": "2026-01-27",')
    ln('  "sku": "岩灰色 512GB"')
    ln("}")
    ln("```")
    ln()
    ln("| 字段 | 类型 | 说明 |")
    ln("|:---|:---|:---|")
    ln("| `id` | string | 唯一标识符（平台前缀 + 原始评论 ID） |")
    ln("| `platform` | string | 来源平台：`jd`、`taobao` 或 `pdd` |")
    ln("| `product` | string | 标准化产品名称（共 10 个取值） |")
    ln("| `content` | string | 评论正文（含追评拼接） |")
    ln("| `date` | string | 评论日期，格式 `YYYY-MM-DD` |")
    ln("| `sku` | string | 购买配置（颜色、存储容量等） |")
    ln()

    # --- 6. 产品列表 ---
    ln("## 六、产品列表")
    ln()
    ln("| 序号 | 产品标识 | 品牌 |")
    ln("|:---|:---|:---|")
    product_brands = {
        "Honor_Magic7_Pro": "荣耀", "Huawei_P70": "华为",
        "OPPO_Find_X9_Pro": "OPPO", "OnePlus_Ace_6T": "一加",
        "Redmi_K90_Pro_Max": "小米（Redmi）", "VIVO_X300_Pro": "VIVO",
        "Xiaomi_15_Pro": "小米", "iPhone_17_Pro": "苹果",
        "iQOO_15": "VIVO（iQOO）", "realme_GT7_Pro": "真我",
    }
    for i, pr in enumerate(products, 1):
        brand = product_brands.get(pr, "")
        ln(f"| {i} | {pr} | {brand} |")
    ln()

    # --- 7. 注意事项 ---
    ln("## 七、使用说明")
    ln()
    ln("- **平台不均衡**：淘宝/天猫占比最大（43.1%），训练时建议按平台分层采样。")
    ln("- **内容质量**：所有系统默认好评已清除，剩余评论均为用户真实评价。")
    ln("- **时间覆盖**：评论跨度约为 2024 年中至 2026 年初，覆盖各产品的首发期和使用期。")
    ln()

    # ================================================================
    report = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ README 已生成: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
