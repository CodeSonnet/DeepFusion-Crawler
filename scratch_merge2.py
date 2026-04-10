import json
import os
import hashlib

base_dir = r"d:\develop\DeepFusion-Crawler\data\JD"
target_file = os.path.join(base_dir, "jd_realme_GT7_Pro.json")
src_files = [
    os.path.join(base_dir, "JD_Comments_1775809027267.json")
]

# Load target data
try:
    with open(target_file, "r", encoding="utf-8") as f:
        target_data = json.load(f)
except Exception as e:
    print(f"Error loading {target_file}: {e}")
    target_data = []

# Keep track of existing content to deduplicate
existing_contents = set()
for item in target_data:
    if item.get("content"):
        existing_contents.add(item["content"].strip())

new_items = []
current_year = "2026"  # based on current time

for src in src_files:
    if not os.path.exists(src):
        print(f"File not found: {src}")
        continue
    with open(src, "r", encoding="utf-8") as f:
        src_data = json.load(f)
    print(f"Loaded {len(src_data)} items from {os.path.basename(src)}")
    
    for item in src_data:
        content = item.get("content", "").strip()
        if not content:
            continue
            
        if content in existing_contents:
            continue
            
        # Format the item
        date_str = item.get("date", "").strip()
        if len(date_str) == 5 and "-" in date_str: # like "03-12"
            date_str = f"{current_year}-{date_str} 00:00:00"
        elif len(date_str) == 10 and date_str.count("-") == 2: # "2025-03-12"
            date_str = f"{date_str} 00:00:00"
        elif not date_str:
            date_str = f"{current_year}-01-01 00:00:00" # fallback
            
        sku_str = item.get("sku", "").strip()
        if sku_str and not sku_str.startswith("已购"):
            sku_str = f"已购 {sku_str}"
            
        # Generate an ID if it's just "0", "1"
        item_id = item.get("id", "")
        if len(item_id) < 5: # likely index
            item_id = "tm_" + hashlib.md5(content.encode()).hexdigest()[:12]
            
        formatted_item = {
            "platform": "JD",
            "product_name": "realme GT7 Pro",
            "id": item_id,
            "content": content,
            "score": 5, # default
            "date": date_str,
            "model_sku": sku_str,
            "append_content": "",
            "votes": 0,
            "images": item.get("images", [])
        }
        new_items.append(formatted_item)
        existing_contents.add(content)

print(f"Adding {len(new_items)} new unique items.")

target_data.extend(new_items)

with open(target_file, "w", encoding="utf-8") as f:
    json.dump(target_data, f, ensure_ascii=False, indent=4)

print(f"Final count: {len(target_data)} items saved to {target_file}")
