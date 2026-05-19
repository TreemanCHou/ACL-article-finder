---
name: acl-article-finder
description: Find ACL Anthology papers for the user's research interests. Use when the user asks to search ACL, EMNLP, NAACL, CoNLL, TACL, or ACL Anthology papers by topic, venue, or year.
disable-model-invocation: true
---

# ACL Article Finder

在 ACL Anthology 网站上查找与用户研究主题相关的论文。优先使用本技能自带脚本抓取和分页读取论文元数据，再由 AI 根据用户兴趣筛选。
注意：
- 你只优先关注我的**主要研究兴趣**，而无需关注我的**次要研究兴趣**。
- 但如果**主要研究兴趣**和**次要研究兴趣**形成了交集，你需要把这些文章的优先级提到最高。
- 如果我没有指定**次要研究兴趣**，你可以忽略。

如果我没有特别交代的话，你可以按这个默认兴趣来搜索。

## 我的主要研究兴趣

知识图谱、知识图谱构建

## 我的次要研究兴趣

语料库、语言学

## 指令

1. 先抓取论文元数据：

```bash
python scripts/fetch_acl_info.py
```

该命令会抓取默认刊物 `ACL`、`EMNLP`、`NAACL`、`CoNLL`、`TACL` 的最新可用年份，并重建 `scripts/cache/`。每次执行都会先清空 cache，避免历史数据过大或混入旧结果。

2. 如果用户指定了刊物或年份，使用命令行参数：

```bash
python scripts/fetch_acl_info.py --venue NAACL --year 2025
python scripts/fetch_acl_info.py --venue ACL --venue EMNLP --year 2024
```

一个 `--year` 会应用到所有 `--venue`；多个 `--year` 必须和 `--venue` 数量一致。脚本会保存标题、来源刊物、年份、论文页面链接和 PDF 下载链接。
需要注意时间。假如用户请求查看的年份是明年甚至未来，你要告诉用户这里有错误；而如果用户请求时，今年的某刊物尚未发布，你可以说明后，查阅该刊物的最新年份。最新年份信息可以在 `https://aclanthology.org/` 看到。

3. 分批读取结果：

```bash
python scripts/show_acl_info.py
```

展示脚本每次默认输出 100 条记录，并维护 `scripts/cache/show_state.json` 作为临时分页指示文件。不要主动清零该指示文件，除非用户明确要求重新从头展示。
你阅读这些记录即可，这一步不必展示给用户。

4. 反复执行展示脚本，直到看到：

```text
ALL PAPERS IS LOADED.
```

5. 每次读到一批论文后，根据论文标题和用户研究兴趣筛选候选论文。按照上述原则，保留与用户研究兴趣相关的论文。注意：
- 你只优先关注我的**主要研究兴趣**，而无需关注我的**次要研究兴趣**。
- 但如果**主要研究兴趣**和**次要研究兴趣**形成了交集，你需要把这些文章放在开头，单独说明他们的存在。
- 如果我没有指定**次要研究兴趣**，你可以忽略。

6. 向用户汇报时，输出相关论文列表即可。每条建议至少包含论文标题、来源刊物和年份、PDF 链接。必要时简短说明为什么相关。


## 输出格式

默认使用 Markdown 列表：

```markdown
- **论文标题**（来源刊物 年份）
  - PDF: https://...
  - 相关原因：...
```

如果结果很多，先给最相关的一小批，并说明仍可继续读取下一批 cache。

## 注意事项

- 不要直接臆造 ACL Anthology 论文信息；以脚本输出的 cache 记录为准。
- 抓取脚本输出文件为 `scripts/cache/papers.json` 和 `scripts/cache/papers.jsonl`。
- 分页展示脚本只负责读取 cache，不会重新抓取网页。
- 如果 `show_acl_info.py` 提示 cache 不存在，先执行 `python scripts/fetch_acl_info.py`。
- 如果用户提供了更具体的关键词，以用户关键词优先；本技能中的研究兴趣作为默认选择标准。