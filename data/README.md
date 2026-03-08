# 🗂️ 跨平台电商手机评论数据集 - 数据文档 (Data Documentation)

本文档是“基于深度学习的跨平台电商评论与消费者决策支持分析”项目的数据集专属说明。
记录了本目录下所有评论数据的资产清单、字段定义（Data Schema）以及数据采集与管理规范，旨在为后续的 Pandas 数据清洗和深度学习模型训练提供标准参考。

---

## 📋 1. 数据资产清单 (Data Inventory)

目前数据源覆盖国内两大核心电商平台（京东、淘宝/天猫），选取了 3 款具有代表性的旗舰机型，共计 6 个 JSON 结构化数据文件。

### 命名规范
文件命名遵循统一的规则：`[平台缩写]_[品牌与机型].json`

### 现有数据文件
* **JD (京东平台 - 侧重物流与正品评价)**
  * 📄 `jd_iphone17_pro.json` (Apple iPhone 17 Pro)
  * 📄 `jd_HuaWei_P70.json` (Huawei P70)
  * 📄 `jd_xiaomi_15_pro.json` (Xiaomi 15 Pro)
* **Taobao/Tmall (淘宝/天猫平台 - 侧重主观体验与多样性评价)**
  * 📄 `taobao_iphone17_pro.json` (Apple iPhone 17 Pro)
  * 📄 `taobao_HuaWei_P70.json` (Huawei P70)
  * 📄 `taobao_xiaomi_15_pro.json` (Xiaomi 15 Pro)

---

## 🏷️ 2. 数据字典 (Data Schema)

为了抹平京东和淘宝底层 API 接口的数据异构性，所有抓取的数据已在采集层进行了统一的字段映射（Mapping）。每个 JSON 对象均包含以下标准化字段：

| 字段名称 (Key) | 数据类型 (Type) | 字段说明 (Description) | 示例值 (Example) |
| :--- | :--- | :--- | :--- |
| `platform` | String | 数据来源的电商平台名称 | `"JD"` 或 `"Taobao/Tmall"` |
| `product_name` | String | 统一对齐后的产品名称，用于跨平台聚合 | `"iPhone 17 Pro Max"` |
| `id` | String | 评论的全局唯一标识符，基于各平台原生评论ID | `"103902930162031324"` |
| `content` | String | 评论的核心正文文本，已去除换行符 | `"拍照效果杠杠的。运行速度相当丝滑..."` |
| `score` | Integer | 用户给出的星级评分 (1-5星) | `5` |
| `date` | String | 评论发布的时间戳或日期字符串 | `"2026-01-27 19:58:21"` |
| `model_sku` | String | 用户购买的详细配置版本（颜色、内存等） | `"已购 星宇橙色 512GB"` |
| `append_content`| String | 用户在使用一段时间后的追加评论（追评） | `"客服处理问题敷衍..."` |
| `votes` | Integer | 该条评论获得的点赞数/有用数 | `7` |
| `images` | List[String] | 评论中附带的买家秀原图 URL 列表 | `["https://img30.360buyimg.com/..."]` |
| `reply` | String | 品牌官方客服在评论下的回复内容（部分平台） | `"感谢您对小店的支持..."` |

---

## ⚙️ 3. 数据采集与管理规范 (Methodology)

### 3.1 采集逻辑
* **接口拦截**: 弃用易被风控的前端 DOM 树解析，采用 `DrissionPage` 监听底层网络包。京东定位 `client.action` 接口，淘宝/天猫定位 `mtop.taobao.rate.detaillist.get` 接口。
* **数据解包**: 针对淘宝特有的 `mtopjsonp` 跨域格式，已在脚本层完成正则剥离，输出为纯净的 JSON 字典。
* **队列清空**: 采集脚本内置 Queue Draining 模式，防止在高速异步加载时漏抓数据。

### 3.2 数据去重与完整性
* 采集过程中以 `id` 字段构建哈希集合（Set），实现了**采集即去重**。
* 即使在网络中断或触发平台滑块验证码时，脚本会触发异常捕获并立即保存当前内存数据，保障了数据资产的安全性。

### 3.3 后续处理建议 (For Data Analysts)
1. **时间格式化**: `date` 字段目前混杂了 `"2025-01-19"` 和 `"2025年3月17日"` 两种格式，建议在 Pandas 预处理阶段统一转化为 `datetime` 对象。
2. **文本清洗**: `content` 和 `append_content` 中可能包含无意义的默认好评（如“此用户没有填写评价”），送入深度学习模型前需进行停用词过滤。
