# -*- coding: utf-8 -*-
"""
Phase 0 数据清洗脚本
规则：
  1. 删除默认好评
  2. 删除单字评论（≤1字）
  3. 拼接追评到 content
  4. 字段统一：id, platform, product, content, date, sku
  5. 拼多多 product_name 归一化
  6. 日期格式统一为 YYYY-MM-DD
  7. ID 加平台前缀避免冲突
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime

# ============================================================
# 配置
# ============================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "cleaned")

# 默认好评关键词（精确匹配：content 完全等于这些内容时才删除）
DEFAULT_PRAISE_EXACT = [
    "该用户觉得商品很好，给出了5星好评",
    "该用户觉得商品较好",
    "该用户未填写文字评价",
    "该用户未填写评价",
    "该用户觉得商品很好，给出了5星评价",
]

# 默认好评关键词（包含匹配：content 中含有这些子串时删除）
DEFAULT_PRAISE_CONTAINS = [
    "此用户未填写评价内容",
    "此用户未及时填写评价内容",
    "该用户未及时主动评价",
    "系统默认评价",
    "系统默认好评",
    "用户未及时评价",
    "此用户没有填写评价内容",
    "买家未在规定时间内评价",
    "用户未做出评价",
    "评价方未及时做出评价",
]

# platform 归一化
PLATFORM_MAP = {
    "JD": "jd",
    "Taobao/Tmall": "taobao",
    "Pinduoduo": "pdd",
}

# product 标准名（从文件名推断）
PRODUCT_RULES = [
    (r"(?i)iphone.?17",         "iPhone_17_Pro"),
    (r"(?i)hua.?wei.?p.?70",    "Huawei_P70"),
    (r"(?i)xiaomi.?15",         "Xiaomi_15_Pro"),
    (r"(?i)vivo.?x.?300",       "VIVO_X300_Pro"),
    (r"(?i)oppo.?find",         "OPPO_Find_X9_Pro"),
    (r"(?i)oneplus.?ace|ace.?6",   "OnePlus_Ace_6T"),
    (r"(?i)redmi.?k.?90|k90",  "Redmi_K90_Pro_Max"),
    (r"(?i)iqoo.?15|iqoo15",   "iQOO_15"),
    (r"(?i)honor|magic.?7|荣耀", "Honor_Magic7_Pro"),
    (r"(?i)realme|gt.?7|真我",  "realme_GT7_Pro"),
]

# 排除的文件（非目标产品）
EXCLUDE_FILES = {"taobao_OnePlus_14.json"}

# ============================================================
# 工具函数
# ============================================================

def infer_product_from_filename(filename):
    """从文件名推断标准产品名"""
    for pattern, product_name in PRODUCT_RULES:
        if re.search(pattern, filename):
            return product_name
    return None


def normalize_platform(raw_platform):
    """平台名归一化"""
    return PLATFORM_MAP.get(raw_platform, raw_platform.lower())


def normalize_date(raw_date):
    """日期格式统一为 YYYY-MM-DD"""
    if not raw_date:
        return ""
    
    raw_date = raw_date.strip()
    
    # 淘宝格式：2026年2月23日
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw_date)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    
    # 标准格式：2026-01-27 19:58:21 → 截取前10字符
    if len(raw_date) >= 10 and raw_date[4] == '-':
        return raw_date[:10]
    
    # 京东缺年份格式：03-15 → 补充 2026-03-15
    m2 = re.match(r"^(\d{2})-(\d{2})$", raw_date)
    if m2:
        return f"2026-{m2.group(1)}-{m2.group(2)}"
    
    return raw_date


def normalize_sku(raw_sku, platform):
    """清理 SKU 字段冗余前缀"""
    if not raw_sku:
        return ""
    
    # 拼多多格式："商品颜色:沙丘金色; 存储容量:256GB; 套餐类型:官方标配; 网络类型:全网通5G"
    if platform == "pdd":
        # 提取键值对，去掉键名，只保留值
        parts = []
        for segment in raw_sku.split(";"):
            segment = segment.strip()
            if ":" in segment:
                _, val = segment.split(":", 1)
                parts.append(val.strip())
            elif segment:
                parts.append(segment)
        return " ".join(parts)
    
    # 淘宝格式："黑色+官方标配[免息分期]+256GB" → 保持原样但清理加号
    if platform == "taobao":
        return raw_sku.replace("+", " ").strip()
    
    # 京东格式："已购 岩灰色 512GB" → 去掉"已购"
    if platform == "jd":
        return re.sub(r"^已购\s*", "", raw_sku).strip()
    
    return raw_sku.strip()


def is_default_praise(content):
    """判断是否为默认好评"""
    content_stripped = content.strip()
    # 精确匹配（拼多多模板）
    if content_stripped in DEFAULT_PRAISE_EXACT:
        return True
    # 包含匹配（京东/淘宝模板）
    for kw in DEFAULT_PRAISE_CONTAINS:
        if kw in content_stripped:
            return True
    return False


def is_too_short(content):
    """判断是否为单字评论（≤1个字符）"""
    # 去除空白和标点后判断
    cleaned = re.sub(r'[\s\W]', '', content)
    return len(cleaned) <= 1


# ============================================================
# 主流程
# ============================================================

def process_file(filepath, filename):
    """处理单个 JSON 文件"""
    product = infer_product_from_filename(filename)
    if product is None:
        print(f"  ⚠️ 无法从文件名推断产品: {filename}，跳过")
        return [], {"skipped_unknown": 1}
    
    with open(filepath, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    
    stats = {
        "raw_count": len(raw_data),
        "removed_default": 0,
        "removed_short": 0,
        "removed_empty": 0,
        "appended": 0,
        "kept": 0,
    }
    
    cleaned = []
    for item in raw_data:
        content = item.get("content", "").strip()
        
        # 空内容直接跳过
        if not content:
            stats["removed_empty"] += 1
            continue
        
        # 追评处理
        append = item.get("append_content", "")
        has_append = append and isinstance(append, str) and append.strip()
        
        # 默认好评判断
        if is_default_praise(content):
            if has_append:
                # 原始内容是默认好评但有追评 → 只保留追评
                content = append.strip()
                stats["appended"] += 1
            else:
                stats["removed_default"] += 1
                continue
        elif has_append:
            content = content + "。" + append.strip()
            stats["appended"] += 1
        
        # 单字评论
        if is_too_short(content):
            stats["removed_short"] += 1
            continue
        
        raw_platform = item.get("platform", "")
        platform = normalize_platform(raw_platform)
        
        cleaned_item = {
            "id": f"{platform}_{item.get('id', '')}",
            "platform": platform,
            "product": product,
            "content": content,
            "date": normalize_date(item.get("date", "")),
            "sku": normalize_sku(item.get("model_sku", ""), platform),
        }
        
        cleaned.append(cleaned_item)
        stats["kept"] += 1
    
    return cleaned, stats


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_reviews = []
    all_stats = []
    platform_data = defaultdict(list)
    
    platforms = ["JD", "TaoBao", "Pinduoduo"]
    
    print("=" * 70)
    print("Phase 0 数据清洗")
    print("=" * 70)
    
    for platform_dir in platforms:
        pdir = os.path.join(DATA_DIR, platform_dir)
        if not os.path.isdir(pdir):
            print(f"⚠️ 目录不存在: {pdir}")
            continue
        
        print(f"\n📂 处理 {platform_dir}/")
        
        files = sorted([f for f in os.listdir(pdir) if f.endswith(".json")])
        for fname in files:
            if fname in EXCLUDE_FILES:
                print(f"  ⏭️ 排除: {fname}")
                continue
            
            fpath = os.path.join(pdir, fname)
            cleaned, stats = process_file(fpath, fname)
            
            if cleaned:
                all_reviews.extend(cleaned)
                p = cleaned[0]["platform"]
                platform_data[p].extend(cleaned)
                
                removed = stats["removed_default"] + stats["removed_short"] + stats["removed_empty"]
                print(f"  ✅ {fname}: {stats['raw_count']} → {stats['kept']} "
                      f"(删除 {removed}: 默认好评{stats['removed_default']}, "
                      f"超短{stats['removed_short']}, 空{stats['removed_empty']}) "
                      f"追评拼接{stats['appended']}")
            
            all_stats.append({"file": fname, "platform": platform_dir, **stats})
    
    # 去重：按 platform + 原始评论ID 去重
    # 拼多多跨店铺共享评论池，同一条评论在不同店铺有相同 ID
    seen_ids = set()
    dedup_reviews = []
    dup_count = 0
    for item in all_reviews:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            dedup_reviews.append(item)
        else:
            dup_count += 1
    
    if dup_count > 0:
        print(f"\n⚠️ 去除跨店铺重复评论: {dup_count} 条")
    
    all_reviews = dedup_reviews
    
    # ============================================================
    # 保存
    # ============================================================
    
    # 1. 全量文件
    out_path = os.path.join(OUTPUT_DIR, "all_reviews.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, ensure_ascii=False, indent=2)
    print(f"\n💾 全量数据已保存: {out_path} ({len(all_reviews)} 条)")
    
    # 2. 按平台分文件
    by_platform_dir = os.path.join(OUTPUT_DIR, "by_platform")
    os.makedirs(by_platform_dir, exist_ok=True)
    for p, items in platform_data.items():
        ppath = os.path.join(by_platform_dir, f"{p}.json")
        with open(ppath, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"💾 {p}.json: {len(items)} 条")
    
    # ============================================================
    # 统计报告
    # ============================================================
    
    print("\n" + "=" * 70)
    print("清洗报告")
    print("=" * 70)
    
    # 产品 × 平台 九宫格
    products = sorted(set(item["product"] for item in all_reviews))
    platforms_clean = ["jd", "taobao", "pdd"]
    
    grid = defaultdict(lambda: defaultdict(int))
    for item in all_reviews:
        grid[item["product"]][item["platform"]] += 1
    
    # 打印表头
    header = f"{'产品':<25}" + "".join(f"{p:>10}" for p in platforms_clean) + f"{'合计':>10}"
    print(header)
    print("-" * len(header))
    
    total_by_platform = defaultdict(int)
    grand_total = 0
    
    for product in products:
        row = f"{product:<25}"
        row_total = 0
        for p in platforms_clean:
            count = grid[product][p]
            row += f"{count:>10}"
            total_by_platform[p] += count
            row_total += count
        row += f"{row_total:>10}"
        grand_total += row_total
        print(row)
    
    print("-" * len(header))
    footer = f"{'合计':<25}" + "".join(f"{total_by_platform[p]:>10}" for p in platforms_clean) + f"{grand_total:>10}"
    print(footer)
    
    # 原始 vs 清洗后
    total_raw = sum(s.get("raw_count", 0) for s in all_stats)
    total_default = sum(s.get("removed_default", 0) for s in all_stats)
    total_short = sum(s.get("removed_short", 0) for s in all_stats)
    total_empty = sum(s.get("removed_empty", 0) for s in all_stats)
    total_appended = sum(s.get("appended", 0) for s in all_stats)
    
    print(f"\n原始总量: {total_raw}")
    print(f"删除默认好评: {total_default}")
    print(f"删除超短评论(≤1字): {total_short}")
    print(f"删除空内容: {total_empty}")
    print(f"去重: {dup_count}")
    print(f"追评拼接: {total_appended}")
    print(f"最终有效: {len(all_reviews)}")
    
    # ============================================================
    # 验证
    # ============================================================
    
    print("\n" + "=" * 70)
    print("数据验证")
    print("=" * 70)
    
    # 1. product 唯一值
    unique_products = set(item["product"] for item in all_reviews)
    print(f"✅ product 唯一值数量: {len(unique_products)} (期望 10)")
    if len(unique_products) != 10:
        print(f"   实际值: {sorted(unique_products)}")
    
    # 2. platform 唯一值
    unique_platforms = set(item["platform"] for item in all_reviews)
    print(f"✅ platform 唯一值: {sorted(unique_platforms)} (期望 jd/taobao/pdd)")
    
    # 3. 30 个格子全覆盖
    empty_cells = [(pr, pl) for pr in unique_products for pl in unique_platforms if grid[pr][pl] == 0]
    if empty_cells:
        print(f"❌ 存在空单元格: {empty_cells}")
    else:
        print(f"✅ 10×3=30 个单元格全覆盖")
    
    # 4. 无重复 ID
    ids = [item["id"] for item in all_reviews]
    if len(ids) == len(set(ids)):
        print(f"✅ 无重复 ID")
    else:
        print(f"❌ 存在重复 ID: {len(ids) - len(set(ids))} 条")
    
    # 5. 无默认好评残留
    default_remain = sum(1 for item in all_reviews if is_default_praise(item["content"]))
    if default_remain == 0:
        print(f"✅ 无默认好评残留")
    else:
        print(f"❌ 仍有 {default_remain} 条默认好评")
    
    # 6. 日期格式检查
    bad_dates = sum(1 for item in all_reviews if not re.match(r"\d{4}-\d{2}-\d{2}$", item.get("date", "")))
    if bad_dates == 0:
        print(f"✅ 所有日期格式正确 (YYYY-MM-DD)")
    else:
        print(f"⚠️ {bad_dates} 条日期格式异常")
        # 打印几个异常样例
        for item in all_reviews:
            if not re.match(r"\d{4}-\d{2}-\d{2}$", item.get("date", "")):
                print(f"   样例: {item['date']}")
                break
    
    # 7. 字段检查
    expected_fields = {"id", "platform", "product", "content", "date", "sku"}
    sample = all_reviews[0]
    actual_fields = set(sample.keys())
    if actual_fields == expected_fields:
        print(f"✅ 字段正确: {sorted(expected_fields)}")
    else:
        print(f"❌ 字段异常: 多余 {actual_fields - expected_fields}, 缺失 {expected_fields - actual_fields}")
    
    # 保存清洗报告
    report_path = os.path.join(OUTPUT_DIR, "cleaning_report.txt")
    # 简单重定向不了，这里就靠终端输出


if __name__ == "__main__":
    main()
