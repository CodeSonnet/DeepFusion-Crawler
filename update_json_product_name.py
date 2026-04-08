import json
import os

def update_product_name(file_path, old_name, new_name):
    if not os.path.exists(file_path):
        print(f"错误: 文件 {file_path} 不存在。")
        return

    try:
        # 读取 JSON 数据
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 统计修改数量
        count = 0
        if isinstance(data, list):
            for item in data:
                if item.get("product_name") == old_name:
                    item["product_name"] = new_name
                    count += 1
        elif isinstance(data, dict):
             if data.get("product_name") == old_name:
                    data["product_name"] = new_name
                    count = 1
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"成功: 已更新 {count} 条记录。")
        print(f"产品名称已从 '{old_name}' 更改为 '{new_name}'。")

    except Exception as e:
        print(f"处理过程中发生错误: {e}")

if __name__ == "__main__":
    target_file = r"d:\develop\DeepFusion-Crawler\data\JD\jd_Redmi_K90_pro_max.json"
    old_val = "OPPO Find X9 Pro "
    new_val = "Redmi K90 pro max"
    
    update_product_name(target_file, old_val, new_val)
