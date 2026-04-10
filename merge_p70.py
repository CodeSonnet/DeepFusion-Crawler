import json
import os

source_file = r"d:\develop\DeepFusion-Crawler\data\taobao_HuaWei_P70.json"
dest_file = r"d:\develop\DeepFusion-Crawler\data\TaoBao\taobao_HuaWei_P70.json"

try:
    with open(dest_file, 'r', encoding='utf-8') as f:
        dest_data = json.load(f)
except Exception as e:
    print(f"Error reading {dest_file}: {e}")
    dest_data = []

try:
    with open(source_file, 'r', encoding='utf-8') as f:
        source_data = json.load(f)
except Exception as e:
    print(f"Error reading {source_file}: {e}")
    source_data = []

# Deduplicate using 'id'
merged_dict = {}
# First, add the destination data
for item in dest_data:
    if 'id' in item:
        merged_dict[item['id']] = item

# Second, add the source data, overwriting duplicates
new_count = 0
dup_count = 0
for item in source_data:
    if 'id' in item:
        if item['id'] in merged_dict:
            dup_count += 1
        else:
            new_count += 1
        merged_dict[item['id']] = item

merged_list = list(merged_dict.values())

# Write back to dest_file
with open(dest_file, 'w', encoding='utf-8') as f:
    json.dump(merged_list, f, ensure_ascii=False, indent=4)

print(f"Merge successful!")
print(f"Original items in dest: {len(dest_data)}")
print(f"Items in source: {len(source_data)}")
print(f"New items added: {new_count}")
print(f"Duplicate items replaced/ignored: {dup_count}")
print(f"Total items in dest now: {len(merged_list)}")
