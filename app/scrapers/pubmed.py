import os
from datetime import datetime
from typing import List, Optional
import requests
from pydantic import BaseModel


class PubMedArticle(BaseModel):
    source_system: str = "pubmed"
    source_id: str             # The PubMed ID (PMID)
    title: str
    abstract: str
    authors: List[str]
    published_date: datetime
    pdf_url: str               


class PubMedScraper:
    def __init__(self):
        self.search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

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

    def _safe_get(self, url: str, params: dict, timeout: int = 15) -> requests.Response:
        """Executes GET request with proxy support and direct fallback if proxy fails."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Connection": "close"
        }
        proxies = self._get_proxies()

        if proxies:
            try:
                response = requests.get(url, params=params, headers=headers, proxies=proxies, timeout=timeout)
                response.raise_for_status()
                return response
            except (requests.exceptions.Timeout, requests.exceptions.ProxyError, requests.exceptions.ConnectionError):
                print(f"[PubMed] Proxy connection failed for {url}. Falling back to direct connection...")

        # Direct connection fallback (or default if no proxies defined)
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def fetch_papers(self, query: str, limit: int = 5, since_date: Optional[datetime] = None) -> List[PubMedArticle]:
        term = query
        if since_date:
            date_str = since_date.strftime("%Y/%m/%d")
            term = f"{query} AND {date_str}[pdat]:3000[pdat]"
            
        search_params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": limit,
            "sort": "pub_date"
        }
        
        try:
            # Step 1: Query for PMIDs matching search terms
            search_response = self._safe_get(self.search_url, params=search_params)
            search_data = search_response.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            
            if not id_list:
                return []

            # Step 2: Request summaries for those specific PMIDs
            summary_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json"
            }
            summary_response = self._safe_get(self.summary_url, params=summary_params)
            summary_data = summary_response.json()
            results = summary_data.get("result", {})

            articles = []
            for pmid in id_list:
                details = results.get(pmid)
                if not details:
                    continue

                authors = [auth.get("name", "") for auth in details.get("authors", [])]
                title = details.get("title", "").strip(".")
                
                pub_date_str = details.get("pubdate", "")
                try:
                    clean_date = datetime.strptime(pub_date_str.split(" ")[0], "%Y")
                except Exception:
                    clean_date = datetime.now()

                articles.append(PubMedArticle(
                    source_id=pmid,
                    title=title,
                    abstract=details.get("sorttitle", ""),
                    authors=authors,
                    published_date=clean_date,
                    pdf_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                ))
            
            return articles

        except Exception as e:
            print(f"[Error] Failed fetching records from PubMed API: {e}")
            return []


if __name__ == "__main__":
    scraper = PubMedScraper()
    print("Testing PubMed Scraper module...")
    results = scraper.fetch_papers(query="cancer immunotherapy", limit=2)
    for paper in results:
        print(f"\n[ID: {paper.source_id}] {paper.title}")
        print(f"URL: {paper.pdf_url}")