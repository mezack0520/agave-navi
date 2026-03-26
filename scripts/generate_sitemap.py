#!/usr/bin/env python3
"""
Auto-generate sitemap.xml from all HTML files in the repository.
Run as part of GitHub Actions or locally.
"""
import os
import glob
from datetime import datetime

DOMAIN = "https://agave-navi.com"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Priority and changefreq settings
PRIORITY_MAP = {
    "index.html": ("1.0", "daily"),
    "ikitai.html": ("0.8", "daily"),
    "calendar.html": ("0.8", "daily"),
    "map.html": ("0.7", "weekly"),
    "listing.html": ("0.7", "monthly"),
    "about.html": ("0.5", "monthly"),
    "contact.html": ("0.5", "monthly"),
    "privacy.html": ("0.3", "yearly"),
    "terms.html": ("0.3", "yearly"),
    "disclaimer.html": ("0.3", "yearly"),
    "operator.html": ("0.3", "yearly"),
}

def get_url(filepath):
    """Convert file path to URL."""
    rel = os.path.relpath(filepath, REPO_ROOT)
    # index.html -> /
    if rel == "index.html":
        return DOMAIN + "/"
    return DOMAIN + "/" + rel

def get_lastmod(filepath):
    """Get last modified date of file."""
    mtime = os.path.getmtime(filepath)
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")

def generate():
    urls = []

    # Collect all HTML files (exclude 404, google verification, etc.)
    html_files = glob.glob(os.path.join(REPO_ROOT, "*.html"))
    html_files += glob.glob(os.path.join(REPO_ROOT, "events", "*.html"))
    html_files += glob.glob(os.path.join(REPO_ROOT, "category", "*.html"))

    for fp in sorted(html_files):
        basename = os.path.basename(fp)
        # Skip non-content pages
        if basename.startswith("google") or basename == "404.html":
            continue

        url = get_url(fp)
        lastmod = get_lastmod(fp)

        # Determine priority and changefreq
        if basename in PRIORITY_MAP:
            priority, changefreq = PRIORITY_MAP[basename]
        elif "/events/" in fp:
            priority, changefreq = "0.8", "weekly"
        elif "/category/" in fp:
            priority, changefreq = "0.6", "weekly"
        else:
            priority, changefreq = "0.5", "monthly"

        urls.append((url, lastmod, changefreq, priority))

    # Generate XML
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    for url, lastmod, changefreq, priority in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{url}</loc>")
        xml_lines.append(f"    <lastmod>{lastmod}</lastmod>")
        xml_lines.append(f"    <changefreq>{changefreq}</changefreq>")
        xml_lines.append(f"    <priority>{priority}</priority>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")

    sitemap_path = os.path.join(REPO_ROOT, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines) + "\n")

    print(f"Generated sitemap.xml with {len(urls)} URLs")
    return sitemap_path

if __name__ == "__main__":
    generate()
