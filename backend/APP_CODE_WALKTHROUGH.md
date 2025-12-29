# app.py 代码逐行详解

这份文档对 `backend/app.py` 进行了逐行解释，帮助理解 YouTube Shorts 分析系统的后端逻辑。

## 1. 导入与配置 (Lines 1-25)

```python
1: from __future__ import annotations
2: import json
3: import os
4: import re
5: from datetime import datetime, timedelta, timezone
6: from pathlib import Path
7: from typing import Dict, List
8: 
9: import requests
10: from dotenv import load_dotenv
11: from flask import Flask, jsonify, request
12: from flask_cors import CORS
```
- **Line 1**: `from __future__ import annotations` 允许在 Python 3.7+ 中使用从类自身引用的类型提示（即暂时无需定义的类型）。
- **Lines 2-7**: 导入 Python 标准库：
  - `json`: 处理 JSON 数据格式。
  - `os`: 操作系统接口，这里主要用于环境变量。
  - `re`: 正则表达式，用于解析时间格式。
  - `datetime`, `timedelta`, `timezone`: 处理日期和时间。
  - `pathlib.Path`: 面向对象的文件系统路径处理库。
  - `typing`: 类型提示支持（`Dict`, `List`）。
- **Line 9**: `import requests`: 第三方库，用于发送 HTTP 请求（这里用于调用 YouTube API）。
- **Line 10**: `from dotenv import load_dotenv`: 用于从 `.env` 文件加载环境变量。
- **Lines 11-12**: Flask 框架相关导入：
  - `Flask`: 创建 Web 应用实例。
  - `jsonify`: 将 Python 字典转换为 JSON 响应。
  - `request`: 获取当前的 HTTP 请求数据。
  - `CORS`: 处理跨域资源共享（Cross-Origin Resource Sharing），允许前端从不同端口请求后端。

```python
14: load_dotenv()
15: 
16: API_KEY = os.getenv("API_KEY")
17: HOST = os.getenv("HOST", "127.0.0.1")
18: PORT = int(os.getenv("PORT", "5000"))
19: ROOT_DIR = Path(__file__).resolve().parents[1]
20: DATA_FILE = ROOT_DIR / "shorts.json"
21: PREVIEW_FILE = ROOT_DIR / "shorts.preview.json"
22: 
23: app = Flask(__name__)
24: CORS(app)
```
- **Line 14**: 加载环境变量。
- **Line 16**: 获取 `API_KEY`，这是访问 YouTube Data API 的凭证。
- **Lines 17-18**: 获取服务器的主机地址和端口，默认分别为 `127.0.0.1` 和 `5000`。
- **Line 19**: 计算项目根目录 (`ROOT_DIR`)。`__file__` 是当前文件路径，`.parents[1]` 指向父目录的父目录（即项目根）。
- **Lines 20-21**: 定义数据存储文件的路径：
  - `shorts.json`: 存储完整数据。
  - `shorts.preview.json`: 存储预览数据（前3条）。
- **Lines 23-24**: 初始化 Flask 应用并启用 CORS，允许跨域请求。

## 2. 辅助功能：时间解析 (Lines 26-61)

```python
26: DURATION_RE = re.compile(
27:     r"PT"  # prefix
28:     r"(?:(?P<hours>\d+)H)?"
29:     r"(?:(?P<minutes>\d+)M)?"
30:     r"(?:(?P<seconds>\d+)S)?",
31:     re.IGNORECASE,
32: )
```
- **Lines 26-32**: 定义一个正则表达式对象 `DURATION_RE`，用于解析 YouTube API 返回的 ISO 8601 持续时间格式（例如 `PT1M5S` 表示1分5秒）。

```python
35: def parse_iso_duration(duration: str) -> int:
36:     match = DURATION_RE.fullmatch(duration)
37:     if not match:
38:         return 0
39:     hours = int(match.group("hours") or 0)
40:     minutes = int(match.group("minutes") or 0)
41:     seconds = int(match.group("seconds") or 0)
42:     return hours * 3600 + minutes * 60 + seconds
```
- **Line 35**: `parse_iso_duration` 函数将 ISO 时间字符串转换为总秒数。
- **Lines 36-42**: 使用正则匹配提取时、分、秒，并计算总秒数。

```python
45: def build_published_after(days: int | None) -> str | None:
46:     if not days:
47:         return None
48:     now = datetime.now(timezone.utc)
49:     target = now - timedelta(days=days)
50:     return target.isoformat().replace("+00:00", "Z")
```
- **Line 45**: `build_published_after` 函数计算“几天前”的时间戳，用于 API 查询参数。
- **Lines 48-50**: 获取当前 UTC 时间，减去指定天数，并格式化为 YouTube API 要求的 RFC 3339 格式（以 `Z` 结尾）。

## 3. YouTube API 调用：按关键词搜索 Shorts (Lines 124-205)

这是核心的数据获取逻辑。

```python
124: def fetch_shorts(keywords: str, max_results: int, days: int | None, region: str | None = None) -> List[Dict]:
125:     if not API_KEY:
126:         raise RuntimeError("API_KEY is not configured in environment")
```
- **Line 124**: `fetch_shorts` 根据关键词搜索 Shorts。
- **Line 125**: 检查 API Key 是否存在。

```python
133:     while len(collected) < max_results:
134:         search_params = {
135:             "key": API_KEY,
136:             "part": "snippet",
137:             "type": "video",
138:             "q": keywords,
139:             "maxResults": per_page,
140:             "order": "viewCount",
141:             "videoDuration": "short",
142:         }
```
- **Lines 133-142**: 构建搜索参数。
  - `q`: 搜索关键词。
  - `videoDuration`: `short` 是关键参数，专门过滤出 Shorts 视频（通常 < 60秒）。
  - `order`: `viewCount` 按播放量排序。

```python
150:         search_resp = requests.get(
151:             "https://www.googleapis.com/youtube/v3/search", params=search_params, timeout=15
152:         )
```
- **Lines 150-152**: 调用 YouTube Search API。

```python
156:         video_ids = [item["id"].get("videoId") for item in search_data.get("items", [])]
...
167:         details_resp = requests.get(
168:             "https://www.googleapis.com/youtube/v3/videos", params=details_params, timeout=15
169:         )
```
- **Lines 156-169**: 搜索 API 只返回基本信息 (`snippet`)，不包含详细统计（播放量、时长）。因此，需要拿到 `videoId` 后，再二次调用 `videos` API 获取详细信息 (`contentDetails`, `statistics`)。

```python
176:             duration_seconds = parse_iso_duration(
177:                 item.get("contentDetails", {}).get("duration", "")
178:             )
179:             if duration_seconds <= 0 or duration_seconds > 60:
180:                 continue
```
- **Lines 176-180**: 再次验证时长。虽然搜索时加了 `videoDuration=short`，但进行二次确认更稳妥。过滤掉 <=0 或 >60秒的视频。

```python
184:             collected.append({
                    "video_id": ...,
                    "title": ...,
                    ...
                    "view_count": int(stats.get("viewCount", 0)),
                    ...
                })
```
- **Lines 184-197**: 将提取清洗后的数据存入 `collected` 列表。

## 5. 数据保存 (Lines 208-217)

```python
208: def save_data(records: List[Dict]) -> Dict:
209:     DATA_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
210:     preview = records[:3]
211:     PREVIEW_FILE.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
212:     return { ... }
```
- **Line 208**: 接收视频记录列表。
- **Line 209**: 将所有记录写入 `shorts.json`。
- **Lines 210-211**: 截取前3条作为预览，写入 `shorts.preview.json`。
- **Line 212**: 返回文件路径和保存数量的统计信息。

## 6. Web 接口 (Lines 220-268)

```python
220: @app.route("/collect", methods=["POST"])
221: def collect():
222:     payload = request.get_json(silent=True) or {}
...
227:     keyword_list = [k.strip() for k in keyword_list_raw if isinstance(k, str) and k.strip()]
```
- **Line 220**: 定义 `/collect` 路由，仅接受 POST 请求。这个接口由前端调用以触发爬虫。
- **Lines 222-236**: 解析并清洗前端传来的关键词列表。支持单个 `keywords` 字符串或 `keyword_list` 数组。

```python
238:     max_results = int(payload.get("max_results") or 20)
239:     days = payload.get("days")
240:     days_int = int(days) if days not in (None, "",) else 7
```
- **Lines 238-240**: 解析参数，设置默认值（默认抓取 20 条，默认时间范围 7 天）。

```python
255:         for kw in keyword_list:
256:             part = fetch_shorts(kw, max_results, days_int, region)
257:             for item in part:
                    ...
263:                     merged[vid] = item
```
- **Lines 255-263**: 遍历每个关键词，调用 `fetch_shorts`。
- **Logic**: 使用字典 `merged` 以 `video_id` 为键进行去重。如果同一个视频被不同关键词搜到，保留播放量较高的那个版本（或者是简单的覆盖，这里代码是 `if not existing or ...`，实际上是同一个视频内容一样，更新一下也没关系）。

```python
264:         records = sorted(merged.values(), key=lambda x: x.get("view_count", 0), reverse=True)[:max_results]
265:         summary = save_data(records)
266:         return jsonify({"total": len(records), "keywords_used": keyword_list, **summary})
```
- **Line 264**: 对所有结果按播放量降序排序，并截取 `max_results` 数量。这意味着如果你搜 3 个关键词，每个关键词分别找 20 条，最后会合并并在所有结果中只返回前 20 条最火的。
- **Lines 265-266**: 保存文件并返回 JSON 响应给前端。

## 7. 程序入口 (Lines 271-272)

```python
271: if __name__ == "__main__":
272:     app.run(host=HOST, port=PORT)
```
- **Lines 271-272**: 如果直接运行此脚本（而不是被导入），则启动 Flask 开发服务器。
