# YouTube Shorts 分析系统

## 版本记录
- v1.1（当前）：关键词必填采集，默认 7 天；前端移除自动采集，修复日志折叠；PRD 同步更新，`.env` 仅本地存放 API Key（不入库）。
- v1：初始脚手架，含后端 `/collect`、前端仪表板骨架、本地化图表库、PRD。

## 使用
1. 准备 `.env`（存放 API_KEY），不提交版本库。
2. 安装依赖：`pip install -r backend/requirements.txt`
3. 运行后端：`python3 backend/app.py`
4. 浏览器打开 `index.html`，输入关键词后采集；采集结果自动写入 `shorts.json` 与 localStorage。
