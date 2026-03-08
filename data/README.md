# 跨平台电商手机评论数据集 (Cross-Platform Smartphone Reviews Dataset)

## 📊 数据集概览
本数据集包含了当前主流三大旗舰智能手机（Apple iPhone 17 Pro, Huawei P70, Xiaomi 15 Pro）在两大头部电商平台（京东、淘宝/天猫）的真实用户带图评论数据。主要用于跨平台多源异构数据的融合分析、细粒度情感计算以及消费者多准则决策（MCDM）模型的研究。

## 📂 文件结构
数据以 JSON 格式存储，按“平台_机型”进行矩阵式分类：
* `jd_iphone17_pro.json`：京东平台 - iPhone 17 Pro 评价数据
* `jd_HuaWei_P70.json`：京东平台 - 华为 P70 评价数据
* `jd_xiaomi_15_pro.json`：京东平台 - 小米 15 Pro 评价数据
* `taobao_iphone17_pro.json`：淘宝/天猫平台 - iPhone 17 Pro 评价数据
* `taobao_HuaWei_P70.json`：淘宝/天猫平台 - 华为 P70 评价数据
* `taobao_xiaomi_15_pro.json`：淘宝/天猫平台 - 小米 15 Pro 评价数据

## 🏷️ 数据字段说明 (Data Schema)
为保证跨平台数据的一致性，提取时已将京东与淘宝的异构底层字段统一映射为以下标准 Schema：

| 字段名 (Field) | 类型 (Type) | 说明 (Description) |
| :--- | :--- | :--- |
| `platform` | String | 数据来源平台（JD 或 Taobao/Tmall） |
| `product_name` | String | 产品统一名称 |
| `id` | String | 评论的唯一标识符（用于全局去重） |
| `content` | String | 评论正文文本 |
| `score` | Integer | 用户打分（1-5星） |
| `date` | String | 评论发布时间 |
| `model_sku` | String | 用户购买的具体配置/颜色型号 |
| `append_content`| String | 用户的追加评论（追评，反映长期使用体验） |
| `votes` | Integer | 该条评论获得的点赞数/有用数（代表群体认同度） |
| `images` | List | 评论附带的真实图片链接集合 |
| `reply` | String | 官方客服的回应文本（部分平台特有） |

## ⚠️ 使用注意事项
1. **数据分布差异**：由于平台心智差异，京东数据的文本通常较长且侧重参数与物流，淘宝数据侧重于服务与主观体验，分析时需注意特征分布的不平衡。
2. **隐私声明**：本数据集仅供学术研究和深度学习模型训练使用，不包含用户敏感个人信息。
