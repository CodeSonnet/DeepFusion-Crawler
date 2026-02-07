# DeepFusion-Crawler
Data acquisition and processing scripts for DeepFusion project.
# DeepFusion Data Acquisition Module

DeepFusion 项目的数据获取与处理模块。

## 📁 目录结构
- `spiders/`: 包含京东、天猫及社交媒体的爬虫脚本 (基于 DrissionPage/Python)。
- `data/`: 数据集样例及字段说明。
- `docs/`: 参考文献与技术文档。

## 🚀 快速开始
1. 安装依赖:
   pip install -r requirements.txt

2. 运行京东爬虫:
   python spiders/jd_spider.py

## 📊 数据字段说明
目标爬取字段包括: `product_id`, `content`, `rating`, `timestamp` 等。
