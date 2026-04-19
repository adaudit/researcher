"""Data acquisition connectors — ScrapCreators API + Scrapling web scraper.

ScrapCreators: 110+ endpoints across 27+ social/ad platforms via single API key.
Scrapling: Anti-bot web crawling, forum scraping, competitor page monitoring.

Architecture:
  ScrapCreators client  →  Platform adapter  →  Existing extractors
  Scrapling scraper     →  page_crawler compat  →  Existing analysis workers
"""
