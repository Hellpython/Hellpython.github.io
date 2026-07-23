# Hellpython.github.io

Hellpython의 프로젝트와 학습 기록을 모은 GitHub Pages 홈페이지입니다.

사이트 주소: https://hellpython.github.io

## 블로그 동기화

Tistory RSS의 최신 글은 매일 09:00 KST에 GitHub Actions로 확인합니다. 변경이 있으면
`data/blog-posts.json`에 누적하고, `index.html`의 `BLOG_RECENT`, `BLOG_SYNC` 구간만
갱신한 뒤 자동으로 commit합니다. RSS에서 오래된 글이 빠져도 archive에는 유지됩니다.

```bash
python3 -m unittest discover -s tests -p "test_*.py"
curl --fail --location https://lessontutor.tistory.com/rss --output /tmp/lessontutor-rss.xml
python3 scripts/sync_blog.py --rss-file /tmp/lessontutor-rss.xml
```

새 글 제목이 기존 분류 규칙과 맞지 않으면 누락하지 않고 `기타`에 표시됩니다.
