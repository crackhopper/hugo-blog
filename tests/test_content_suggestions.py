import tempfile
import unittest
from pathlib import Path

from hugo_blog.pipeline.content_suggestions import suggest_article_moves


class FakeCompleter:
    def __init__(self, payload):
        self.payload = payload
        self.prompts = []

    def complete_json(self, *, prompt: str, system: str = "只输出严格 JSON。", temperature: float = 0.2):
        self.prompts.append(prompt)
        return self.payload


class ContentSuggestionsTest(unittest.TestCase):
    def test_suggests_sanitized_post_targets_from_llm_choices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts" / "图形学").mkdir(parents=True)
            article = content / "posts" / "draft.md"
            article.write_text(
                "---\ntitle: Vulkan 入门 01\ntags:\n- Vulkan\n---\n正文\n",
                encoding="utf-8",
            )
            completer = FakeCompleter(
                {
                    "suggestions": [
                        {
                            "target_path": "content/posts/图形学/Vulkan/Vulkan 入门:01.md",
                            "title": "Vulkan 入门 01",
                            "reason": "属于图形学 Vulkan 系列。",
                        },
                        {
                            "target_path": "../bad.md",
                            "title": "Bad",
                            "reason": "fallback",
                        },
                    ]
                }
            )

            suggestions = suggest_article_moves(content_dir=content, rel_path="posts/draft.md", llm_client=completer)

            self.assertEqual(suggestions[0].target_path, "posts/图形学/Vulkan/Vulkan_入门_01.md")
            self.assertEqual(suggestions[0].title, "Vulkan 入门 01")
            self.assertIn("已有目录: posts/图形学", completer.prompts[0])
            self.assertEqual(suggestions[1].target_path, "posts/bad.md")

    def test_returns_fallback_when_llm_payload_is_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            content = Path(temp_dir) / "content"
            (content / "posts").mkdir(parents=True)
            (content / "posts" / "draft.md").write_text("---\ntitle: Draft\n---\n", encoding="utf-8")

            suggestions = suggest_article_moves(
                content_dir=content,
                rel_path="posts/draft.md",
                llm_client=FakeCompleter({"suggestions": []}),
            )

            self.assertEqual(suggestions[0].target_path, "posts/draft.md")
            self.assertEqual(suggestions[0].title, "Draft")


if __name__ == "__main__":
    unittest.main()
