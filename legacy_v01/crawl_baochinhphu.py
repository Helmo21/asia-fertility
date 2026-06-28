"""Crawl https://en.baochinhphu.vn/ up to 5 layers deep using crawl4ai.

Uses BFS deep-crawling restricted to the en.baochinhphu.vn domain.
Writes each page's markdown + metadata to ./crawl_output/.
"""
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import DomainFilter, FilterChain

START_URL = "https://en.baochinhphu.vn/"
MAX_DEPTH = 5
MAX_PAGES = 300
OUTPUT_DIR = Path(__file__).parent / "crawl_output"


def slugify_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/") or "index"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{parsed.netloc}_{path}")
    return slug[:180]


async def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    filter_chain = FilterChain([DomainFilter(allowed_domains=["en.baochinhphu.vn"])])
    strategy = BFSDeepCrawlStrategy(
        max_depth=MAX_DEPTH,
        include_external=False,
        max_pages=MAX_PAGES,
        filter_chain=filter_chain,
    )

    browser_cfg = BrowserConfig(headless=True, verbose=False)
    run_cfg = CrawlerRunConfig(
        deep_crawl_strategy=strategy,
        cache_mode=CacheMode.BYPASS,
        stream=True,
        verbose=False,
        page_timeout=45_000,
    )

    index: list[dict] = []

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        async for result in await crawler.arun(START_URL, config=run_cfg):
            depth = result.metadata.get("depth", 0) if result.metadata else 0
            ok = result.success
            url = result.url
            print(f"[depth={depth} ok={ok}] {url}")
            if not ok:
                index.append({"url": url, "depth": depth, "ok": False, "error": result.error_message})
                continue

            slug = slugify_url(url)
            md_path = OUTPUT_DIR / f"d{depth}__{slug}.md"
            md = result.markdown.raw_markdown if hasattr(result.markdown, "raw_markdown") else str(result.markdown)
            md_path.write_text(md or "", encoding="utf-8")
            index.append({
                "url": url,
                "depth": depth,
                "ok": True,
                "title": (result.metadata or {}).get("title"),
                "file": md_path.name,
                "internal_links": len(result.links.get("internal", [])) if result.links else 0,
                "external_links": len(result.links.get("external", [])) if result.links else 0,
            })

    (OUTPUT_DIR / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    by_depth: dict[int, int] = {}
    for row in index:
        by_depth[row["depth"]] = by_depth.get(row["depth"], 0) + 1
    print("\n=== Summary ===")
    print(f"Total pages: {len(index)}")
    for d in sorted(by_depth):
        print(f"  depth {d}: {by_depth[d]} pages")
    print(f"Output dir: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
