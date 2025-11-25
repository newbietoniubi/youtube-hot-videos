# YouTube Shorts 分析系统 PRD（macOS 版本，无授权）

## 1. 项目背景与目标
- 复刻并优化 v2.0 描述的 YouTube Shorts 数据收集与分析系统，去除激活码流程，专供个人 macOS 使用。
- 目标：在 macOS 下提供一键数据采集（通过本地后端代理）、离线/本地化 HTML 仪表板展示、报告导出，支持大规模数据（最高 1 万条）和月度深度分析。

## 2. 用户与场景
- 个人研究者/创作者：按关键词、时间范围批量获取 Shorts 数据，用于趋势分析、选题参考。
- 使用场景：快速采样（50-100）、中等趋势观察（500-1000）、大规模研究（5000-10000）。

## 3. 功能需求
### 3.1 数据采集（本地后端 API）
- 形态：轻量本地后端（Python Flask/FastAPI 或 Node/Express），仅本机可访问。
- API Key：仅存放于后端 `.env`（或环境变量），不写入前端代码，前端不可见。
- 输入参数（由前端调用本地 API）：关键词、最大结果数（50-10000）、可选“最近 N 天”过滤（留空=全量）。
- Shorts 过滤：后端限定 `duration_seconds <= 60`。
- API 时间过滤：`publishedAfter` 由“最近 N 天”计算，传递给 YouTube Data API v3。
- 排序：采集结果按观看次数降序排序后保存（热门优先）。
- 结果输出：后端写 `shorts.json`（全量）与 `shorts.preview.json`（前 3 条）到项目目录；返回采集摘要。
- 错误提示：API Key 缺失/无效、配额不足、网络错误、无结果；前端展示。

### 3.2 数据分析仪表板（HTML，本地文件）
- 数据来源：优先读取浏览器 `localStorage`；若无则加载同目录 `shorts.json` 并写入 `localStorage`。可提供“触发采集”按钮调用本地后端 `/collect`。
- 采集成功后自动将新数据写入 localStorage 并渲染（无需手动加载按钮）。
- 统计卡：视频总数、观看总数、点赞总数、评论总数、平均观看、平均点赞。
- 图表（先不指定图表库，后续确认）：互动分布、时长分布、观看-点赞散点、发布时间趋势（按月）、热门频道、标签词云、参与度雷达、观看分布饼图。
- 时间轴交互：点击月份跳转到 `analytics_detail.html?date=YYYY-MM`，仅显示该月数据。
- 热门频道跳转：点击频道条目打开对应 YouTube 频道（新标签页）。
- 分页：热门视频列表支持 10/20/50/100 条，智能显示上一页/下一页。
- 热门视频列表：标题可点击，跳转对应 YouTube 视频（新标签页）。
- 热门视频列表默认按观看次数从高到低排序显示。
- 导出报告：生成 JSON 包含总体统计、前 20 热门视频、前 10 热门频道、前 20 标签。

### 3.3 月度详情页（HTML）
- 通过 URL 查询参数 `date=YYYY-MM` 过滤 `localStorage` 中数据，渲染月度专属统计与图表。

### 3.4 配置与持久化
- API Key 后端环境变量/.env 存储，前端不可见。
- 数据本地存储：`shorts.json`、`shorts.preview.json` 与应用同目录；浏览器侧 `localStorage` 用于自动加载。

## 4. 非功能需求
- 平台：macOS（Python 3.10+ 或 Node 18+），后端仅本机运行；可选 PyInstaller/Nexe 打包但非必需。
- 离线友好：仪表板可本地打开；图表库后续可本地化引入；采集需联网访问 YouTube API。
- 性能：1 万条视频数据下前端渲染可接受（必要时做懒加载/分页）。
- 安全：不含授权/卡密逻辑；API Key 仅本地存储（编码非加密）。

## 5. 数据结构（`shorts.json` 元素）
```json
{
  "video_id": "string",
  "title": "string",
  "channel_id": "string",
  "channel_title": "string",
  "published_at": "ISO 8601 string",
  "duration_seconds": 56,
  "view_count": 5201,
  "like_count": 344,
  "comment_count": 0,
  "tags": ["tag1","tag2"]
}
```

## 6. 交互/流程
1) 配置：在本地后端 `.env` 写入 API Key。
2) 采集：前端调用本地后端 `/collect`，传关键词/最大数/可选天数 → 后端请求 YouTube API（服务端时间过滤 + 短视频过滤 + 数量上限）→ 写 `shorts.json` 与 `shorts.preview.json` → 返回摘要。
3) 加载：打开 `index.html` → 若 `localStorage` 有数据直接渲染；否则读取 `shorts.json` 并写入 `localStorage`。
4) 分析：浏览统计卡与图表；热门频道可点击跳转；热门视频分页浏览；一键导出报告。
5) 月度详情：在发布时间趋势图点击月份 → 新标签页 `analytics_detail.html?date=YYYY-MM` → 按月过滤数据并渲染。

## 7. 文件与目录（建议）
- `backend/`：本地后端（Python Flask/FastAPI 或 Node/Express），包含 `.env.example`、依赖文件。
- `shorts.json` / `shorts.preview.json` / `api_key.txt`（若用 Python 存储 Key 编码）：运行产物。
- `index.html`：总览仪表板。
- `analytics_detail.html`：月度详情页。
- `assets/`（可选）：本地图表库、样式。

## 8. 待确认/后续决策
- 图表库：ECharts、本地打包 Chart.js 还是其他；若需离线则本地引入。
- 后端栈：Python（Flask/FastAPI）或 Node（Express/Koa）；默认选 Python + Flask。
- 是否需要打包：是否将后端打包为 `.app`/可执行文件。

## 9. 风险与对策
- API 配额不足 → 明确提示，并允许减少最大结果数或增大时间范围。
- 大数据量前端性能 → 必要时启用分页/懒加载、降采样散点数据。
- 网络限制 → 本地化图表库和字体资源，确保离线可用；采集阶段需外网访问 YouTube API。

## 10. 开发计划
- 环境/骨架：确定后端栈（默认 Python+Flask），初始化虚拟环境，创建 `backend/`，编写 `.env.example`（含 API_KEY），列出依赖。
- 后端实现：编写 `/collect` 接口，接收关键词/最大数/最近 N 天，调用 YouTube Data API v3，执行短视频过滤（<=60s）和数量上限，写入 `shorts.json`/`shorts.preview.json`，返回摘要与错误信息。
- 前端对接：在 `index.html` 添加“触发采集”表单/按钮，调用本地 `/collect`，成功后写入 localStorage 并触发渲染。
- 仪表板完善：按 PRD 补齐统计卡、图表占位、分页、月度详情跳转；图表库待定但预留挂载点。
- 本地化与路径：确保前端优先读取 localStorage，缺失时读同目录 JSON；约定数据文件路径一致。
- 测试验证：用小规模数据跑通采集→渲染；验证无/错 API Key、配额不足、无结果等错误提示。
- 后续（可选）：引入本地图表库（ECharts/Chart.js）、性能优化（1 万条分页/懒加载）、后端打包为可执行或 `.app`。
