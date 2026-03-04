import json
import os

# 定义文件名
file_1 = 'jd_iphone17_pro.json' # 含有图片和点赞的那个
file_2 = 'iphone17_pro.json'    # 另一个

# 读取数据
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

data1 = load_json(file_1)
data2 = load_json(file_2)

# 使用字典进行合并去重（以 id 为键）
# 策略：优先保留字段更全的 data1，如果 data2 有新 id 则加入
merged_dict = {}

# 先放 data2 (较旧/字段较少的)
for item in data2:
    if 'id' in item:
        merged_dict[item['id']] = item

# 再放 data1 (较新/字段较全的)，如果有重复 id，data1 会覆盖 data2
for item in data1:
    if 'id' in item:
        merged_dict[item['id']] = item

# 转回列表
final_data = list(merged_dict.values())

print(f"文件1 数量: {len(data1)}")
print(f"文件2 数量: {len(data2)}")
print(f"合并后总数量: {len(final_data)}")

# 保存
with open('jd_iphone17_final_merged.json', 'w', encoding='utf-8') as f:
    json.dump(final_data, f, ensure_ascii=False, indent=4)