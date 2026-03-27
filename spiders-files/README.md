# 拼多多评论爬虫使用指南

本工具通过拼多多移动版API抓取商品搜索结果和评论数据。

## 目录

- [环境要求](#环境要求)
- [Cookie获取方法](#cookie获取方法)
- [安装配置](#安装配置)
- [使用方法](#使用方法)
- [输出格式](#输出格式)
- [常见问题](#常见问题)

---

## 环境要求

- Python 3.8+
- 仅依赖 `requests` 库（标准库，无需额外安装）

```bash
# 检查Python版本
python --version

# requests库通常已预装，如有需要可执行
pip install requests
```

---

## Cookie获取方法

Cookie是拼多多API的身份验证凭证，必须从浏览器获取。

### 步骤一：打开拼多多网页

1. 使用Chrome或Edge浏览器访问：https://mobile.yangkeduo.com
2. **必须登录账号**（未登录无法获取评论），推荐使用在手机上登陆过的账号，扫码登陆网页版。

### 步骤二：打开开发者工具

按 `F12` 打开开发者工具，选择 **Network（网络）** 标签。

### 步骤三：刷新页面触发请求

按下 `F5` 刷新页面，Network面板会显示所有网络请求。

### 步骤四：找到任意请求获取Cookie

1. 在Network面板左侧点击任意一个请求（通常是第一个）
2. 在右侧 **Headers** 面板中找到 **Request Headers**
3. 找到 `Cookie:` 字段，复制其完整值

### 步骤五：更新脚本中的Cookie

打开 `PDD_Crawler_Script.py`，找到第264行附近的 `COOKIE` 变量，将复制的内容粘贴替换。

```python
COOKIE = """这里是你复制的Cookie内容"""
```

### 重要提示

- **Cookie有效期**：Cookie通常有有效期限制，过期后需要重新获取
- **账号安全**：Cookie相当于登录凭证，请勿泄露给他人
- **建议**：经常使用时建议定期更换Cookie

---

## 安装配置

### 1. 克隆/下载项目

```bash
git clone <项目地址>
cd DeepFusion-Crawler/spiders-files
```

### 2. 配置Cookie

按照上文说明获取并更新Cookie。

### 3. 创建数据目录

脚本会自动创建 `data/Pinduoduo` 目录保存数据，如需手动创建：

```bash
mkdir -p ../data/Pinduoduo
```

---

## 使用方法

### 模式一：仅搜索商品

根据关键词搜索商品，获取商品ID、名称、价格、销量等信息。

```bash
python PDD_Crawler_Script.py search "关键词"
```

**示例：**
```bash
python PDD_Crawler_Script.py search "华为pura70"
python PDD_Crawler_Script.py search "充电宝"
```

**输出文件：** `data/Pinduoduo/search_关键词.json`

---

### 模式二：仅获取评论

根据商品ID获取该商品的全部评论。

```bash
python PDD_Crawler_Script.py reviews "商品ID"
```

**示例：**
```bash
python PDD_Crawler_Script.py reviews 921751342960
python PDD_Crawler_Script.py reviews 923049167279
```

**输出文件：** `data/Pinduoduo/reviews_商品ID.json`

---

### 模式三：搜索+获取评论（推荐）

自动搜索关键词商品，然后逐一抓取每个商品的评论。

```bash
python PDD_Crawler_Script.py all "关键词"
```

**示例：**
```bash
python PDD_Crawler_Script.py all "华为pura70"
python PDD_Crawler_Script.py all "手机壳"
```

**输出文件：** `data/Pinduoduo/all_reviews_关键词.json`

---

### 参数说明

| 模式 | 参数 | 说明 | 默认值 |
|------|------|------|--------|
| search | 关键词 | 搜索商品的关键字 | "华为pura70" |
| reviews | 商品ID | 拼多多商品ID | "921751342960" |
| all | 关键词 | 搜索并抓取评论 | "华为pura70" |

### 代码调用示例

如需在Python代码中调用：

```python
from PDD_Crawler_Script import PinduoduoCrawler, save_json

# 初始化爬虫（使用默认Cookie）
crawler = PinduoduoCrawler()

# 方式1：搜索商品
goods = crawler.search_all_goods("华为pura70", max_pages=3)

# 方式2：获取单个商品评论
reviews = crawler.get_all_reviews("921751342960", max_pages=50)

# 方式3：搜索+抓取评论
keyword = "华为pura70"
goods = crawler.search_all_goods(keyword, max_pages=3)

all_reviews = []
for i, g in enumerate(goods[:5]):
    print(f"\n[{i+1}/5] 处理商品: {g['goods_name']}")
    reviews = crawler.get_all_reviews(g['goods_id'], max_pages=20)
    for r in reviews:
        r['product_name'] = g['goods_name']
    all_reviews.extend(reviews)

save_json(all_reviews, f"all_reviews_{keyword}.json")
```

---

## 输出格式

### 商品数据结构 (search)

```json
{
  "goods_id": "923049167279",
  "goods_name": "华为Pura70 5G手机",
  "price": 5999.00,
  "sales": "10万+",
  "mall_name": "华为官方旗舰店",
  "link": "https://mobile.yangkeduo.com/goods.html?goods_id=923049167279"
}
```

### 评论数据结构 (reviews)

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "content": "手机收到了，非常好用，拍照效果很棒！",
  "score": 5,
  "date": "2026-03-15 14:30:00",
  "model_sku": "颜色:玄黑;内存:256GB",
  "append_content": "",
  "votes": 128,
  "images": [
    "https://img.pddpic.com/..."
  ],
  "reply": "感谢支持，欢迎再次光临！",
  "platform": "Pinduoduo",
  "product_name": "华为Pura70 5G手机",
  "goods_id": "923049167279"
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| id | 评论唯一ID（MD5哈希） |
| content | 评论正文内容 |
| score | 评分（1-5星） |
| date | 评论时间 |
| model_sku | 商品规格型号 |
| append_content | 追评内容 |
| votes | 点赞数 |
| images | 评论图片URL列表 |
| reply | 商家回复 |
| platform | 平台标识（固定为"Pinduoduo"） |
| product_name | 商品名称 |
| goods_id | 商品ID |

---

## 常见问题

### Q: 搜索返回空结果怎么办？

**A:** 可能原因：
1. Cookie已过期 → 重新获取Cookie
2. 关键词无搜索结果 → 尝试其他关键词
3. 网络问题 → 检查网络连接

### Q: 评论API返回空数据？

**A:** 可能原因：
1. **Cookie过期** → 这是最常见原因，需要重新获取
2. 商品ID不存在或无效 → 确认商品ID正确
3. 商品无评论 → 尝试其他商品

### Q: 如何判断Cookie是否有效？

**A:** 运行搜索命令，如果能返回商品列表说明Cookie有效；如果评论返回0条说明Cookie可能已过期。

### Q: 抓取速度可以加快吗？

**A:** 脚本已有随机延时保护。如需调整，可以修改代码中的延时参数：
- `time.sleep(random.uniform(0.3, 0.8))` - 评论翻页延时
- `time.sleep(random.uniform(0.5, 1.5))` - 搜索翻页延时

### Q: 数据保存在哪里？

**A:** 默认保存在 `data/Pinduoduo/` 目录下，文件名格式：
- 搜索：`search_关键词.json`
- 评论：`reviews_商品ID.json`
- 全部：`all_reviews_关键词.json`

---

## 免责声明

本工具仅供学习研究使用，请勿用于商业用途或任何违反拼多多用户协议的行为。抓取数据时，请遵守网站的robots.txt规则和相关法律法规。
