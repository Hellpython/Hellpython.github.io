"""sitemap.xml과 feed.xml이 실제 페이지와 어긋나면 실패하는 staleness guard.

새 페이지(특히 daily 기록)를 추가하고 sitemap/feed 갱신을 잊으면
이 테스트가 먼저 알려준다.
"""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://hellpython.github.io"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

SKIP_DIRS = {".git", "assets", "data", "scripts", "tests", "node_modules"}


def site_pages():
    """저장소에서 실제로 서비스되는 페이지 경로 집합 ('/', '/daily/' 형태)."""
    pages = set()
    for index in ROOT.rglob("index.html"):
        rel = index.relative_to(ROOT).parent
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        pages.add("/" if not rel.parts else f"/{rel.as_posix()}/")
    return pages


def sitemap_paths():
    tree = ET.parse(ROOT / "sitemap.xml")
    return {urlparse(loc.text.strip()).path for loc in tree.findall(".//s:loc", SITEMAP_NS)}


class SitemapTest(unittest.TestCase):
    def test_sitemap_matches_actual_pages(self):
        actual = site_pages()
        listed = sitemap_paths()
        self.assertEqual(actual - listed, set(), "sitemap.xml에 누락된 페이지")
        self.assertEqual(listed - actual, set(), "sitemap.xml에 존재하지 않는 페이지")

    def test_sitemap_urls_use_site_base(self):
        tree = ET.parse(ROOT / "sitemap.xml")
        for loc in tree.findall(".//s:loc", SITEMAP_NS):
            self.assertTrue(loc.text.startswith(BASE + "/"), loc.text)


class FeedTest(unittest.TestCase):
    def setUp(self):
        self.tree = ET.parse(ROOT / "feed.xml")

    def test_feed_has_required_atom_elements(self):
        root = self.tree.getroot()
        for tag in ("id", "title", "updated"):
            self.assertIsNotNone(root.find(f"a:{tag}", ATOM_NS), f"feed에 <{tag}> 없음")
        for entry in root.findall("a:entry", ATOM_NS):
            for tag in ("id", "title", "updated", "link"):
                self.assertIsNotNone(entry.find(f"a:{tag}", ATOM_NS), f"entry에 <{tag}> 없음")

    def test_feed_links_resolve_to_existing_pages(self):
        pages = site_pages()
        for link in self.tree.findall(".//a:entry/a:link", ATOM_NS):
            path = urlparse(link.get("href")).path
            self.assertIn(path, pages, f"feed entry가 없는 페이지를 가리킴: {path}")

    def test_every_daily_entry_is_in_feed(self):
        daily_pages = {p for p in site_pages() if p.startswith("/daily/20")}
        feed_paths = {
            urlparse(link.get("href")).path
            for link in self.tree.findall(".//a:entry/a:link", ATOM_NS)
        }
        missing = daily_pages - feed_paths
        self.assertEqual(missing, set(), f"feed.xml에 누락된 daily 기록: {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()
