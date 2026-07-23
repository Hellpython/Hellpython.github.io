#!/usr/bin/env python3
"""Sync the Tistory RSS feed into the generated homepage blocks."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse


RSS_URL = "https://lessontutor.tistory.com/rss"
MAX_FEED_BYTES = 2_000_000


@dataclass(frozen=True)
class Post:
    title: str
    link: str
    published: datetime
    category: str

    @property
    def display_date(self) -> str:
        return self.published.strftime("%Y.%m.%d")


CATEGORY_ORDER = ("javascript", "backend", "os", "network", "other")
CATEGORY_META = {
    "javascript": (
        "JavaScript",
        "모던 JavaScript Deep Dive를 읽고 정리한 내용과 학습 기록을 모읍니다.",
    ),
    "backend": (
        "Backend & 인프라",
        "서버 운영 환경과 cache 기술처럼 Backend를 지탱하는 도구와 선택 기준을 정리합니다.",
    ),
    "os": (
        "운영체제",
        "프로세스, 메모리, 파일 시스템처럼 Backend 개발의 기반이 되는 운영체제 개념을 정리합니다.",
    ),
    "network": (
        "네트워크",
        "HTTP, TCP/IP, DNS처럼 서버와 client가 통신하는 흐름을 공부하며 정리합니다.",
    ),
    "other": (
        "기타",
        "아직 별도 분야로 묶이지 않은 새로운 학습 기록입니다.",
    ),
}


def categorize(title: str, feed_categories: tuple[str, ...] = ()) -> str:
    text = " ".join((title, *feed_categories)).lower()

    if any(keyword in text for keyword in ("javascript", "자바스크립트", "프로그래밍")):
        return "javascript"
    if any(
        keyword in text
        for keyword in (
            "socket",
            "네트워크",
            "스위치",
            "mac 주소",
            "ip 주소",
            "reverse proxy",
            "osi ",
            "tcp/ip",
            "dns",
            "http",
        )
    ):
        return "network"
    if "운영체제" in text or re.search(r"(^|[^a-z])os([^a-z]|$)", text):
        return "os"
    if any(
        keyword in text
        for keyword in (
            "backend",
            "백엔드",
            "라즈베리파이",
            "ubuntu",
            "server",
            "redis",
            "valkey",
            "memcached",
            "cache",
            "database",
            "docker",
            "linux",
            "nginx",
            "api",
        )
    ):
        return "backend"
    return "other"


def validate_post_link(link: str) -> None:
    parsed = urlparse(link)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "lessontutor.tistory.com"
        or not parsed.path.startswith("/entry/")
    ):
        raise ValueError(f"unexpected blog URL: {link}")


def parse_rss(payload: bytes) -> list[Post]:
    root = ET.fromstring(payload)
    posts: list[Post] = []
    seen_links: set[str] = set()

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        feed_categories = tuple(
            category.text.strip()
            for category in item.findall("category")
            if category.text and category.text.strip()
        )

        if not title or not link or not pub_date:
            raise ValueError("RSS item is missing title, link, or pubDate")
        validate_post_link(link)
        if link in seen_links:
            continue

        seen_links.add(link)
        posts.append(
            Post(
                title=title,
                link=link,
                published=parsedate_to_datetime(pub_date),
                category=categorize(title, feed_categories),
            )
        )

    if not posts:
        raise ValueError("RSS feed contains no posts")
    return sorted(posts, key=lambda post: post.published, reverse=True)


def fetch_rss(url: str = RSS_URL) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Hellpython.github.io RSS sync"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("RSS feed exceeds the 2 MB safety limit")
    return payload


def render_recent(post: Post) -> str:
    label = CATEGORY_META[post.category][0]
    return "\n".join(
        (
            f'          <a class="recent-card" href="{html.escape(post.link, quote=True)}">',
            f"            <h3>{html.escape(post.title)}</h3>",
            '            <span class="recent-card-meta">',
            '              <span class="record-type">블로그</span>',
            f"              <span>{post.display_date} · {html.escape(label)}</span>",
            "            </span>",
            "          </a>",
        )
    )


def render_topic(category: str, posts: list[Post]) -> str:
    title, description = CATEGORY_META[category]
    count = len(posts)
    lines = [
        f'          <section class="topic" data-category="{category}">',
        '            <div class="topic-heading-row">',
        f"              <h2>{html.escape(title)}</h2>",
        f'              <span class="topic-count" aria-label="{count}개 기록">{count}</span>',
        "            </div>",
        f"            <p>{html.escape(description)}</p>",
        '            <ul class="note-list">',
    ]
    for post in posts:
        lines.extend(
            (
                "              <li>",
                f'                <a class="note-title" href="{html.escape(post.link, quote=True)}">{html.escape(post.title)}</a>',
                f'                <span class="note-meta">블로그에서 보기 · {post.display_date}</span>',
                "              </li>",
            )
        )
    lines.extend(("            </ul>", "          </section>"))
    return "\n".join(lines)


def render_topics(posts: list[Post]) -> str:
    groups = {category: [] for category in CATEGORY_ORDER}
    for post in posts:
        groups[post.category].append(post)
    return "\n\n".join(
        render_topic(category, groups[category])
        for category in CATEGORY_ORDER
        if groups[category]
    )


def merge_posts(existing: list[Post], incoming: list[Post]) -> list[Post]:
    merged = {post.link: post for post in existing}
    for post in incoming:
        previous = merged.get(post.link)
        if previous:
            post = Post(post.title, post.link, post.published, previous.category)
        merged[post.link] = post
    return sorted(merged.values(), key=lambda post: post.published, reverse=True)


def load_archive(path: Path) -> list[Post]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("posts"), list):
        raise ValueError("unsupported blog archive format")

    posts = []
    for item in payload["posts"]:
        validate_post_link(item["link"])
        if item["category"] not in CATEGORY_META:
            raise ValueError(f"unknown archived category: {item['category']}")
        posts.append(
            Post(
                title=item["title"],
                link=item["link"],
                published=datetime.fromisoformat(item["published"]),
                category=item["category"],
            )
        )
    return posts


def serialize_archive(posts: list[Post]) -> str:
    payload = {
        "version": 1,
        "posts": [
            {
                "title": post.title,
                "link": post.link,
                "published": post.published.isoformat(),
                "category": post.category,
            }
            for post in posts
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def replace_block(page: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(?P<start><!-- {re.escape(name)}:START -->)\n.*?\n(?P<end>\s*<!-- {re.escape(name)}:END -->)",
        re.DOTALL,
    )
    updated, count = pattern.subn(
        lambda match: f'{match.group("start")}\n{body}\n{match.group("end")}',
        page,
        count=1,
    )
    if count != 1:
        raise ValueError(f"expected one {name} marker block, found {count}")
    return updated


def update_page(page: str, posts: list[Post]) -> str:
    page = replace_block(page, "BLOG_RECENT", render_recent(posts[0]))
    return replace_block(page, "BLOG_SYNC", render_topics(posts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rss-file", type=Path, help="Use a local RSS fixture instead of the network")
    parser.add_argument("--output", type=Path, default=Path("index.html"))
    parser.add_argument("--archive", type=Path, default=Path("data/blog-posts.json"))
    parser.add_argument("--check", action="store_true", help="Fail when the homepage is not current")
    args = parser.parse_args()

    payload = args.rss_file.read_bytes() if args.rss_file else fetch_rss()
    feed_posts = parse_rss(payload)
    posts = merge_posts(load_archive(args.archive), feed_posts)
    current = args.output.read_text(encoding="utf-8")
    updated = update_page(current, posts)
    current_archive = args.archive.read_text(encoding="utf-8") if args.archive.exists() else ""
    updated_archive = serialize_archive(posts)

    if args.check:
        if current != updated or current_archive != updated_archive:
            print("homepage or blog archive is not synchronized", file=sys.stderr)
            return 1
        print(f"RSS sync check passed: {len(feed_posts)} feed posts, {len(posts)} archived posts")
        return 0

    if current == updated and current_archive == updated_archive:
        print(f"No update needed: {len(posts)} archived posts")
        return 0

    args.output.write_text(updated, encoding="utf-8")
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    args.archive.write_text(updated_archive, encoding="utf-8")
    print(f"Updated homepage and archive: {len(feed_posts)} feed posts, {len(posts)} total posts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
