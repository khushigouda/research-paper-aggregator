import os
import time
from datetime import datetime, timezone
from typing import List, Optional
import requests
import xml.etree.ElementTree as ET
from pydantic import BaseModel


class ArXivPaper(BaseModel):
    source_system: str = "arxiv"
    source_id: str             
    title: str
    abstract: str
    authors: List[str]
    published_date: datetime
    pdf_url: str


class ArXivScraper:
    def __init__(self):
        # http connection avoids TLS handshake/proxy hangs with arXiv's Fastly CDN
        self.base_url = "http://export.arxiv.org/api/query"

    def _get_proxies(self) -> Optional[dict]:
        """Fetches proxy configuration from environment variables if set."""
        http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
        
        proxies = {}
        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy
            
        return proxies if proxies else None

    def fetch_papers(self, query: str, limit: int = 10, since_date: Optional[datetime] = None) -> List[ArXivPaper]:
        params = {
            "search_query": query,
            "start": 0,
            "max_results": limit,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/atom+xml,application/xml",
            "Connection": "close"  # Instructs server to close connection after response
        }

        papers = []
        try:
            # Respect arXiv rate limit window
            time.sleep(1.0)
            
            proxies = self._get_proxies()
            
            # If proxies are configured in environment, attempt proxy request first
            if proxies:
                try:
                    response = requests.get(
                        self.base_url,
                        params=params,
                        headers=headers,
                        proxies=proxies,
                        timeout=25
                    )
                except (requests.exceptions.Timeout, requests.exceptions.ProxyError):
                    print("[arXiv] Proxy connection timed out or failed. Attempting direct connection fallback...")
                    response = requests.get(
                        self.base_url,
                        params=params,
                        headers=headers,
                        timeout=25
                    )
            else:
                # Direct connection path
                response = requests.get(
                    self.base_url,
                    params=params,
                    headers=headers,
                    timeout=25
                )

            response.raise_for_status()
            
            # Parse Atom XML directly
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
                summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
                
                published_str = entry.find('atom:published', ns).text
                published_at = datetime.fromisoformat(published_str.replace('Z', '+00:00'))

                if since_date:
                    if since_date.tzinfo is None:
                        since_date = since_date.replace(tzinfo=timezone.utc)
                    if published_at < since_date:
                        continue

                # ID Parsing
                raw_id = entry.find('atom:id', ns).text
                short_id = raw_id.split('/abs/')[-1]

                # Authors
                authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]

                # PDF Link
                pdf_url = f"https://arxiv.org/pdf/{short_id}.pdf"

                papers.append(ArXivPaper(
                    source_id=short_id,
                    title=title,
                    abstract=summary,
                    authors=authors,
                    published_date=published_at,
                    pdf_url=pdf_url
                ))

        except Exception as e:
            print(f"[Error] Failed to read entries from arXiv API: {e}")

        return papers


if __name__ == "__main__":
    scraper = ArXivScraper()
    print("Testing arXiv Scraper...")
    results = scraper.fetch_papers(query="quantum computing", limit=2)
    for paper in results:
        print(f"\n[ID: {paper.source_id}] {paper.title}")