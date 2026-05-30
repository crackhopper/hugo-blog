# `src/hugo_blog/pipeline/reports.py`

这个文件是 normalize 报告对象的兼容导出层。

## 主要职责

导出：

- `NormalizeReport`
- `print_report`

## 修改注意

报告结构目前定义在 `normalize.py`。如果报告逻辑继续增长，可以考虑把类型和打印函数迁移到这个文件。
