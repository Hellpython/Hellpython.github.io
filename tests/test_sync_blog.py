import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_blog import (  # noqa: E402
    Post,
    categorize,
    merge_posts,
    parse_rss,
    render_recent,
    render_topics,
    update_page,
)


SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Socket basics</title>
    <link>https://lessontutor.tistory.com/entry/socket-basics</link>
    <pubDate>Mon, 13 Jul 2026 09:00:00 +0900</pubDate>
    <category>CS/Network</category>
  </item>
  <item>
    <title>Redis &amp; cache</title>
    <link>https://lessontutor.tistory.com/entry/redis-cache</link>
    <pubDate>Sun, 12 Jul 2026 09:00:00 +0900</pubDate>
  </item>
  <item>
    <title>Socket basics duplicate</title>
    <link>https://lessontutor.tistory.com/entry/socket-basics</link>
    <pubDate>Sat, 11 Jul 2026 09:00:00 +0900</pubDate>
  </item>
</channel></rss>"""


class SyncBlogTests(unittest.TestCase):
    def test_known_titles_are_classified(self):
        self.assertEqual(categorize("JavaScript 표현식과 문"), "javascript")
        self.assertEqual(categorize("OS는 왜 필요할까?"), "os")
        self.assertEqual(categorize("MAC 주소와 IP 주소"), "network")
        self.assertEqual(categorize("Redis와 Valkey"), "backend")
        self.assertEqual(categorize("새로운 공부"), "other")

    def test_rss_is_sorted_and_deduplicated(self):
        posts = parse_rss(SAMPLE_RSS)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].title, "Socket basics")
        self.assertEqual(posts[1].category, "backend")

    def test_unexpected_origin_is_rejected(self):
        payload = SAMPLE_RSS.replace(
            b"https://lessontutor.tistory.com/entry/socket-basics",
            b"https://example.com/entry/socket-basics",
        )
        with self.assertRaisesRegex(ValueError, "unexpected blog URL"):
            parse_rss(payload)

    def test_rendered_content_contains_counts_and_escaped_links(self):
        posts = parse_rss(SAMPLE_RSS)
        topics = render_topics(posts)
        recent = render_recent(posts[0])
        self.assertIn('data-category="network"', topics)
        self.assertIn('aria-label="1개 기록"', topics)
        self.assertIn("2026.07.13", recent)

    def test_only_marker_blocks_are_replaced(self):
        page = """before
<!-- BLOG_RECENT:START -->
old recent
<!-- BLOG_RECENT:END -->
middle
<!-- BLOG_SYNC:START -->
old topics
<!-- BLOG_SYNC:END -->
after"""
        updated = update_page(page, parse_rss(SAMPLE_RSS))
        self.assertTrue(updated.startswith("before"))
        self.assertTrue(updated.endswith("after"))
        self.assertNotIn("old recent", updated)
        self.assertNotIn("old topics", updated)

    def test_backslashes_in_titles_are_preserved(self):
        posts = parse_rss(SAMPLE_RSS)
        posts[0] = Post(
            title=r"경로 \1 기록",
            link=posts[0].link,
            published=posts[0].published,
            category=posts[0].category,
        )
        page = """<!-- BLOG_RECENT:START -->
old
<!-- BLOG_RECENT:END -->
<!-- BLOG_SYNC:START -->
old
<!-- BLOG_SYNC:END -->"""
        self.assertIn(r"경로 \1 기록", update_page(page, posts))

    def test_archive_merge_keeps_posts_missing_from_rolling_feed(self):
        feed_posts = parse_rss(SAMPLE_RSS)
        older = Post(
            title="이전 기록",
            link="https://lessontutor.tistory.com/entry/older-post",
            published=feed_posts[-1].published.replace(year=2025),
            category="other",
        )
        merged = merge_posts([older], feed_posts)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[-1], older)


if __name__ == "__main__":
    unittest.main()
