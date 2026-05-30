import unittest

from hugo_blog.pipeline.markdown_document import parse_markdown_document


class MarkdownDocumentTest(unittest.TestCase):
    def test_detects_front_matter_summary_marker_and_first_heading(self):
        text = """---
title: 已有文章
tags:
  - cpp
draft: false
---
这是一段已有摘要。

<!-- more -->

# 第一个标题
正文
"""

        document = parse_markdown_document(text)

        self.assertTrue(document.has_front_matter)
        self.assertEqual(document.front_matter["title"], "已有文章")
        self.assertEqual(document.summary, "这是一段已有摘要。")
        self.assertEqual(document.first_heading_line, 11)

    def test_detects_compact_more_marker(self):
        document = parse_markdown_document("摘要\n\n<!--more-->\n\n# 标题\n正文")

        self.assertEqual(document.summary, "摘要")


if __name__ == "__main__":
    unittest.main()
