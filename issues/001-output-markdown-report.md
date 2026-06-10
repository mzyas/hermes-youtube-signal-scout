# Feature Request: `--output-md` Markdown 报告输出

**状态:** 已完成
**优先级:** 中
**日期:** 2026-06-10

---

## 目标

搜索结果除了 JSON，还能直接输出 `.md` 报告到指定目录，方便在 Obsidian 等工具中直接查看。

## 需求

### 1. 新增配置项 `output_dir`

- 类型: `str | None`
- 默认值: `None`（不输出 md）
- 在 `skill.yaml` 的 `defaults` 中可预设

### 2. 自动生成 Markdown

每次 `filter_and_rank` 完成后，若 `config.output_dir` 不为空，自动生成文件：

```
{output_dir}/{topic}_{timestamp}.md
{output_dir}/{topic}_{timestamp}.json   ← JSON 也同步输出
```

### 3. Markdown 模板

```markdown
# {topic} · 最近7天 YouTube 信号

**生成时间:** {created_at}
**搜索 query:** `{query}`
**时间范围:** {published_after} ~ {published_before|至今}
**配额消耗:** {quota_cost} units (search×N, videos×N)
**通过/过滤:** {accepted}/{rejected}

---

## 通过筛选 ({N} 条)

| # | 得分 | 标题 | 频道 | 发布日期 | 时长 | 播放量 |
|---|------|------|------|----------|------|--------|
| 1 | 0.49 | [title](url) | channel | YYYY-MM-DD | mm:ss | N,N,N |

---

## 被过滤 ({N} 条)

| # | 标题 | 原因 |
|---|------|------|
| 1 | title | reason |

---

*由 hermes-youtube-signal-scout v{version} 生成*
```

### 4. 标题转义

`title` 中的 `|` 需转义为 `\|`，避免破坏 markdown 表格语法。

## 实现建议

### 新增文件: `tools/md_writer.py`

```python
def write_markdown_report(output: dict, output_dir: str, config: dict) -> str:
    """Render filter_and_rank output as markdown, return file path."""
```

### 集成点

在搜索入口（如 `search_videos` 调用链末尾）检查 `config.get("output_dir")`，存在则同时调用 `md_writer.write_markdown_report()`。

### 参考实现

`/tmp/yt_md.py`（本次会话中已验证可行的实现）

## 期望默认路径

```
E:\[Loc]Skill本地输出位置\hermes-youtube-signal-scout输出\
```

建议写入 `skill.yaml`：

```yaml
defaults:
  output_dir: "E:\\\\[Loc]Skill本地输出位置\\\\hermes-youtube-signal-scout输出"
```

## 实现进度

已于 2026-06-10 完成：

- 新增 	ools/md_writer.py，生成同名 Markdown 和 JSON 报告。
- ilter_and_rank() 在 output_dir 非空时自动写出报告，并返回 output_files。
- skill.yaml 与输入 schema 新增可选 output_dir，默认值为 
ull。
- 结果 schema 新增可选 output_files。
- 新增 	ests/test_md_writer.py，覆盖 Markdown 表格、JSON 输出、文件名、标题转义和默认无副作用行为。
- 全量离线测试：16 tests OK；Codex Skill 校验通过。
## 验收标准

- [x] `config.output_dir` 为空时不生成 md（向后兼容）
- [x] md 文件包含完整表格：得分、标题（可点击）、频道、日期、时长、播放量
- [x] 被过滤视频表格包含过滤原因
- [x] 标题中的 `|` 正确转义
- [x] JSON 文件同步输出到同目录
- [x] 文件名包含 topic + 时间戳
