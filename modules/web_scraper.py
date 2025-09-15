import requests
import time
import re
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
import logging
from asyncio_throttle import Throttler
from config import Config
from modules.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)

class WebScraper:
    """Web scraper for company information enrichment"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.ua = UserAgent()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.llm_extractor = None
        if self.config.USE_LLM_SCRAPING:
            try:
                self.llm_extractor = LLMExtractor(self.config)
            except Exception as e:
                logger.warning(f"LLM extractor unavailable: {e}")
    
    async def search_person_info(self, full_name: str, company_name: str = "", email: str = "") -> Dict[str, Any]:
        """Search for information about a person using web search with concurrent requests"""
        try:
            import urllib.parse
            
            # Create comprehensive search queries for finding information about the person
            search_queries = []
            
            # Extract first and last name for more flexible searches
            name_parts = full_name.split()
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[-1] if len(name_parts) > 1 else ''
            
            if company_name:
                search_queries.extend([
                    f'"{full_name}" {company_name} CEO founder executive director manager',
                    f'"{full_name}" {company_name} linkedin profile',
                    f'{full_name} {company_name} "job title" OR "position" OR "role"',
                    f'"{first_name} {last_name}" {company_name} biography about'
                ])
            
            email_domain = ''
            if email:
                domain = email.split('@')[1] if '@' in email else ''
                if domain and domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com']:
                    email_domain = domain
                    search_queries.extend([
                        f'"{full_name}" site:{domain} about team',
                        f'{first_name} {last_name} site:{domain} founder CEO director'
                    ])
            
            # Add general search
            search_queries.append(f'"{full_name}" linkedin profile')
            
            results = {}
            
            # Process all queries concurrently
            for query in search_queries:  # Remove slice restriction - process all queries
                logger.info(f"Searching for person info: {query}")
                
                # Search all engines concurrently
                search_results = await self._search_all_engines_async(query, full_name, company_name)
                
                # Merge results from all engines
                for engine_name, engine_results in search_results.items():
                    if engine_results:
                        results.update(engine_results)
                        logger.info(f"Found results from {engine_name}: {engine_results}")
                
                # If we found what we need, can break early
                if results.get('linkedin_url') and results.get('job_title'):
                    break
            
            # If we didn't find specific job info but have email domain, try to infer from web scraping quickly
            if not results.get('job_title') and email_domain:
                logger.info(f"Attempting to infer job role from company website for {email_domain}")
                # Try to scrape the company website to understand the business
                try:
                    company_url = f"https://{email_domain}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(company_url, timeout=5) as response:
                            if response.status == 200:
                                content = await response.text()
                                company_context = self._extract_company_context(content)
                                if company_context.get('company_type'):
                                    inferred_role = self._infer_job_role_from_company_type(
                                        company_context['company_type'], email_domain
                                    )
                                    if inferred_role:
                                        results['job_title'] = inferred_role
                                        results['job_title_source'] = 'inferred_from_company_type'
                                        logger.info(f"Inferred job role '{inferred_role}' from company type '{company_context['company_type']}'")
                except Exception as e:
                    logger.debug(f"Could not infer role from company website: {e}")
            
            if results:
                logger.info(f"Successfully found person info for {full_name}: {results}")
            else:
                logger.info(f"No person info found for {full_name}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching for person info {full_name}: {e}")
            return {}

    async def _search_all_engines_async(self, query: str, full_name: str, company_name: str) -> Dict[str, Dict[str, Any]]:
        """Search all engines concurrently for the given query"""
        import urllib.parse
        
        # Define all search engines
        search_engines = [
            ("DuckDuckGo", f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"),
            ("Bing", f"https://www.bing.com/search?q={urllib.parse.quote(query)}"),
            ("Google", f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        async def search_single_engine(session, engine_name, search_url):
            """Search a single engine"""
            try:
                logger.debug(f"Searching {engine_name}: {query}")
                
                async with session.get(search_url, timeout=8, headers=headers) as response:
                    if response.status == 200:
                        content = await response.text()
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        results = {}
                        if self._parse_search_results(soup, engine_name, full_name, company_name, results):
                            logger.info(f"Found results from {engine_name}")
                            return {engine_name: results}
                        
                        # Check for LinkedIn URLs and follow top result links
                        await self._parse_and_follow_links(session, soup, engine_name, full_name, company_name, results)
                        
                        if results:
                            return {engine_name: results}
                    
                return {engine_name: {}}
                        
            except Exception as e:
                logger.debug(f"{engine_name} search failed: {e}")
                return {engine_name: {}}
        
        # Execute all searches concurrently
        async with aiohttp.ClientSession() as session:
            tasks = [search_single_engine(session, engine_name, search_url) 
                    for engine_name, search_url in search_engines]
            
            search_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine results
        combined_results = {}
        for result in search_results:
            if isinstance(result, dict):
                combined_results.update(result)
        
        return combined_results
    
    async def _parse_and_follow_links(self, session, soup: BeautifulSoup, engine_name: str, 
                                     full_name: str, company_name: str, results: dict) -> None:
        """Parse search results and follow top result links for additional information"""
        try:
            # Get top N search result links to follow
            result_links = []
            
            if engine_name == "DuckDuckGo":
                search_result_divs = soup.find_all('div', class_='result__body') or soup.find_all('div', class_='web-result')
                for div in search_result_divs[:3]:  # Top 3 results
                    link_elem = div.find('a', href=True)
                    if link_elem:
                        result_links.append(link_elem['href'])
            elif engine_name == "Bing":
                search_result_divs = soup.find_all('li', class_='b_algo')[:3]
                for div in search_result_divs:
                    link_elem = div.find('a', href=True)
                    if link_elem:
                        result_links.append(link_elem['href'])
            elif engine_name == "Google":
                search_result_divs = soup.find_all('div', class_='g')[:3]
                for div in search_result_divs:
                    link_elem = div.find('a', href=True)
                    if link_elem:
                        result_links.append(link_elem['href'])
            
            # Follow promising links that might contain job info
            for link in result_links:
                if any(keyword in link.lower() for keyword in ['linkedin', 'about', 'team', 'biography', 'profile']):
                    try:
                        async with session.get(link, timeout=5) as response:
                            if response.status == 200:
                                content = await response.text()
                                page_soup = BeautifulSoup(content, 'html.parser')
                                page_text = page_soup.get_text()[:2000]  # First 2000 chars
                                
                                # Extract job title and industry info from the linked page
                                if self._contains_job_info(page_text, full_name):
                                    person_info = self._extract_person_info(page_text, full_name, company_name)
                                    if person_info:
                                        results.update(person_info)
                                        logger.info(f"Found person info from linked page ({engine_name}): {person_info}")
                                        
                    except Exception as e:
                        logger.debug(f"Failed to follow link {link}: {e}")
                        continue
                        
        except Exception as e:
            logger.debug(f"Error following links for {engine_name}: {e}")
    
    def _parse_search_results(self, soup: BeautifulSoup, engine_name: str, full_name: str, company_name: str, results: dict) -> bool:
        """Parse search results from different search engines"""
        found_info = False
        
        try:
            # Different selectors for different search engines
            if engine_name == "DuckDuckGo":
                search_results = soup.find_all('div', class_='result__body') or soup.find_all('div', class_='web-result')
            elif engine_name == "Bing":
                search_results = soup.find_all('li', class_='b_algo') or soup.find_all('div', class_='b_title')
            elif engine_name == "Google":
                search_results = soup.find_all('div', class_='g') or soup.find_all('div', class_='rc')
            else:
                search_results = soup.find_all('div', class_='result')
            
            # Also get raw text as fallback
            raw_text = soup.get_text()[:3000]  # First 3000 chars
            
            # Process search results
            for result in search_results[:8]:
                try:
                    result_text = result.get_text() if result else ''
                    
                    # Look for LinkedIn URLs with multiple patterns
                    linkedin_patterns = [
                        r'linkedin\.com/in/([a-zA-Z0-9\-_]+)',
                        r'linkedin\.com/pub/([a-zA-Z0-9\-_]+)',
                        r'(?:https?://)?(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_]+)/?'
                    ]
                    
                    for pattern in linkedin_patterns:
                        linkedin_matches = re.findall(pattern, result_text, re.IGNORECASE)
                        if linkedin_matches and 'linkedin_url' not in results:
                            username = linkedin_matches[0]
                            linkedin_url = f"https://www.linkedin.com/in/{username}"
                            results['linkedin_url'] = linkedin_url
                            logger.info(f"Found LinkedIn URL via {engine_name}: {linkedin_url}")
                            found_info = True
                            break
                    
                    # Enhanced job title and person info extraction
                    combined_text = result_text + ' ' + raw_text[:1000]
                    
                    if self._contains_job_info(combined_text, full_name):
                        person_info = self._extract_person_info(combined_text, full_name, company_name)
                        if person_info:
                            results.update(person_info)
                            logger.info(f"Found person info via {engine_name}: {person_info}")
                            found_info = True
                    
                    # Look for company confirmation
                    if company_name and self._check_company_confirmation(combined_text, company_name, full_name):
                        results['company_confirmed'] = True
                        found_info = True
                        
                except Exception as e:
                    logger.debug(f"Error processing {engine_name} result: {e}")
                    continue
            
            # Also check raw text for LinkedIn URLs and job info
            if not found_info:
                linkedin_matches = re.findall(r'linkedin\.com/in/([a-zA-Z0-9\-_]+)', raw_text, re.IGNORECASE)
                if linkedin_matches and 'linkedin_url' not in results:
                    username = linkedin_matches[0]
                    linkedin_url = f"https://www.linkedin.com/in/{username}"
                    results['linkedin_url'] = linkedin_url
                    logger.info(f"Found LinkedIn URL in raw text via {engine_name}: {linkedin_url}")
                    found_info = True
                
                if self._contains_job_info(raw_text, full_name):
                    person_info = self._extract_person_info(raw_text, full_name, company_name)
                    if person_info:
                        results.update(person_info)
                        logger.info(f"Found person info in raw text via {engine_name}: {person_info}")
                        found_info = True
            
            return found_info
            
        except Exception as e:
            logger.debug(f"Error parsing {engine_name} results: {e}")
            return False
    
    def _check_company_confirmation(self, text: str, company_name: str, full_name: str) -> bool:
        """Check if text confirms person works at company"""
        try:
            company_variations = [
                company_name.lower(),
                company_name.lower().replace(' ', ''),
                company_name.lower().replace(' ', '-'),
                company_name.lower().replace(' ', '_')
            ]
            text_lower = text.lower()
            name_lower = full_name.lower()
            
            return any(var in text_lower for var in company_variations) and name_lower in text_lower
            
        except Exception:
            return False
    
    def _contains_job_info(self, text: str, person_name: str) -> bool:
        """Check if text contains relevant job/professional information"""
        job_keywords = [
            'CEO', 'CTO', 'CFO', 'COO', 'CMO', 'CSO', 'founder', 'co-founder', 'president', 
            'director', 'manager', 'executive', 'head of', 'vice president', 'VP', 'chief', 
            'lead', 'senior', 'principal', 'partner', 'owner', 'supervisor', 'coordinator',
            'specialist', 'analyst', 'consultant', 'advisor', 'chairman', 'board member'
        ]
        
        text_lower = text.lower()
        
        # Check different name variations
        name_parts = person_name.split()
        first_name = name_parts[0].lower() if name_parts else ''
        last_name = name_parts[-1].lower() if len(name_parts) > 1 else ''
        full_name_lower = person_name.lower()
        
        # Check if any name variation is in text
        name_in_text = (
            full_name_lower in text_lower or 
            (first_name and last_name and f"{first_name} {last_name}" in text_lower) or
            (first_name and len(first_name) > 2 and first_name in text_lower)
        )
        
        # Check for job keywords
        has_job_keywords = any(keyword.lower() in text_lower for keyword in job_keywords)
        
        return name_in_text and has_job_keywords
    
    def _extract_company_context(self, text: str) -> Dict[str, Any]:
        """Extract company context and type from text"""
        context = {}
        
        try:
            text_lower = text.lower()
            
            # Identify company types from text
            company_types = {
                'design agency': ['presentation design', 'design agency', 'creative agency', 'branding agency'],
                'consulting': ['consulting', 'advisory', 'management consulting', 'business consulting'],
                'technology': ['software', 'tech company', 'startup', 'saas', 'platform', 'app development'],
                'marketing': ['marketing agency', 'digital marketing', 'advertising agency'],
                'finance': ['investment', 'financial services', 'fintech', 'banking'],
                'healthcare': ['medical', 'healthcare', 'pharmaceutical', 'biotech'],
                'real estate': ['real estate', 'property development', 'construction']
            }
            
            for company_type, keywords in company_types.items():
                if any(keyword in text_lower for keyword in keywords):
                    context['company_type'] = company_type
                    break
            
            return context
            
        except Exception as e:
            logger.debug(f"Error extracting company context: {e}")
            return {}
    
    def _infer_job_role_from_company_type(self, company_type: str, email_domain: str = '') -> Optional[str]:
        """Infer likely job role based on company type for email domain matches"""
        
        # Common senior roles by company type
        role_mapping = {
            'design agency': 'Creative Director',
            'consulting': 'Senior Consultant', 
            'technology': 'CTO',
            'marketing': 'Marketing Director',
            'finance': 'Financial Director',
            'healthcare': 'Medical Director',
            'real estate': 'Development Director'
        }
        
        return role_mapping.get(company_type)
    
    def _extract_person_info(self, text: str, full_name: str, company_name: str) -> Dict[str, Any]:
        """Extract person information from text"""
        info = {}
        
        try:
            # More comprehensive job title patterns
            job_patterns = [
                # Standard titles
                r'\b(?:CEO|CTO|CFO|COO|CMO|CSO|founder|co-founder|president|director|manager|executive|head of|VP|chief|lead|senior|principal|partner|owner)\b[^\n]*',
                # Vice president patterns
                r'\b(?:vice\s+president|chief\s+\w+\s+officer)\b[^\n]*',
                # "Name is" or "Name, Title" patterns
                rf'\b{re.escape(full_name.split()[0])}[^\n]*?\b(?:is|serves as|works as)\s+(?:a|an|the)?\s*([^\n,\.]+?)(?:at|for|of)',
                rf'\b{re.escape(full_name)}[^\n]*?,\s*([^\n,\.]+?)(?:at|for|of)',
                # Job title before name
                r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+' + re.escape(full_name.split()[0]),
            ]
            
            text_lines = text.replace('\n', ' ').replace('  ', ' ')
            
            for pattern in job_patterns:
                matches = re.findall(pattern, text_lines, re.IGNORECASE)
                if matches:
                    # Clean up the match
                    title = matches[0].strip()
                    # Remove common prefixes/suffixes
                    title = re.sub(r'^(is|serves as|works as|the|a|an)\s+', '', title, flags=re.IGNORECASE)
                    title = re.sub(r'\s+(at|for|of|in)\s+.*$', '', title, flags=re.IGNORECASE)
                    if len(title) > 5 and len(title) < 50:  # Reasonable title length
                        info['job_title'] = title.title()
                        break
            
            # Look for company mentions
            if company_name and company_name.lower() in text.lower():
                info['company_confirmed'] = True
            
            # Enhanced industry keyword detection
            industry_keywords = {
                'Technology': ['tech', 'software', 'AI', 'artificial intelligence', 'machine learning', 'data', 'cloud', 'SaaS', 'startup', 'digital', 'platform', 'app development', 'cybersecurity', 'blockchain'],
                'Finance': ['financial', 'banking', 'investment', 'fintech', 'trading', 'insurance', 'wealth management', 'private equity', 'venture capital'],
                'Healthcare': ['healthcare', 'medical', 'pharmaceutical', 'biotech', 'health', 'hospital', 'clinic', 'wellness', 'medical device'],
                'Consulting': ['consulting', 'advisory', 'strategy', 'management consulting', 'business consulting'],
                'Marketing': ['marketing', 'advertising', 'digital marketing', 'social media', 'brand', 'communications', 'PR'],
                'Real Estate': ['real estate', 'property', 'construction', 'development', 'architecture'],
                'Manufacturing': ['manufacturing', 'production', 'industrial', 'automotive', 'aerospace'],
                'Education': ['education', 'university', 'school', 'academic', 'learning', 'training'],
                'Legal': ['law', 'legal', 'attorney', 'lawyer', 'litigation'],
                'Retail': ['retail', 'e-commerce', 'consumer goods', 'fashion', 'apparel']
            }
            
            text_lower = text.lower()
            for industry, keywords in industry_keywords.items():
                if any(keyword in text_lower for keyword in keywords):
                    info['industry_hint'] = industry
                    break
            
            return info
            
        except Exception as e:
            logger.error(f"Error extracting person info: {e}")
            return info
        
    def get_company_info_from_website(self, website_url: str, company_name: str = "") -> Dict[str, Any]:
        """Scrape company information from their website. If enabled, use LLM extraction with fallback."""
        try:
            if not website_url or not website_url.startswith(('http://', 'https://')):
                if website_url and not website_url.startswith(('http://', 'https://')):
                    website_url = f"https://{website_url}"
                else:
                    return {}
            
            response = self.session.get(website_url, timeout=10)
            response.raise_for_status()
            
            html_text = response.text
            soup = BeautifulSoup(response.content, 'html.parser')
            
            company_info = {
                'website': website_url,
                'company_size': '',
                'industry': '',
                'revenue_estimate': '',
                'company_year_est': '',
                'description': ''
            }
            
            # Prefer LLM extraction if enabled
            used_llm = False
            if self.llm_extractor is not None:
                try:
                    llm_info = self.llm_extractor.extract_company_info(
                        html_text=html_text,
                        website_url=website_url,
                        company_name_hint=company_name,
                    )
                    # Merge LLM results first
                    for key in ['company_size','industry','revenue_estimate','company_year_est','description']:
                        if llm_info.get(key):
                            company_info[key] = llm_info[key]
                    used_llm = any(company_info.get(k) for k in ['company_size','industry','revenue_estimate','company_year_est','description'])
                except Exception as e:
                    logger.debug(f"LLM extraction failed: {e}")

            # Heuristic extraction as fallback or to fill gaps
            if not used_llm or True:
                company_info.update(self._extract_from_about_page(soup, website_url))
                company_info.update(self._extract_from_meta_tags(soup))
                company_info.update(self._extract_from_structured_data(soup))
                company_info.update(self._extract_industry_keywords(soup))
            
            # Try to get more info from about page
            about_url = self._find_about_page_url(soup, website_url)
            if about_url:
                try:
                    about_response = self.session.get(about_url, timeout=10)
                    about_soup = BeautifulSoup(about_response.content, 'html.parser')
                    company_info.update(self._extract_from_about_page(about_soup, about_url))
                except Exception as e:
                    logger.debug(f"Could not scrape about page {about_url}: {e}")
            
            logger.info(f"Scraped company info from {website_url}")
            return company_info
            
        except Exception as e:
            logger.error(f"Error scraping website {website_url}: {e}")
            return {}
    
    def _extract_from_meta_tags(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract information from meta tags"""
        info = {}
        
        # Description from meta tags
        description_meta = soup.find('meta', attrs={'name': 'description'}) or \
                          soup.find('meta', attrs={'property': 'og:description'})
        if description_meta:
            info['description'] = description_meta.get('content', '').strip()
        
        # Industry from keywords
        keywords_meta = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_meta:
            keywords = keywords_meta.get('content', '').lower()
            info['industry'] = self._classify_industry_from_keywords(keywords)
        
        return info
    
    def _extract_from_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract information from structured data (JSON-LD)"""
        info = {}
        
        # Look for JSON-LD structured data
        json_ld_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})
        for script in json_ld_scripts:
            try:
                import json
                data = json.loads(script.string)
                
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                # Extract organization data
                if data.get('@type') in ['Organization', 'Corporation', 'LocalBusiness']:
                    if data.get('foundingDate'):
                        info['company_year_est'] = str(data['foundingDate'])[:4]
                    
                    if data.get('numberOfEmployees'):
                        employees = data['numberOfEmployees']
                        if isinstance(employees, dict):
                            info['company_size'] = f"{employees.get('minValue', '')}-{employees.get('maxValue', '')}"
                        else:
                            info['company_size'] = str(employees)
                    
                    if data.get('description'):
                        info['description'] = data['description']
                        
                    if data.get('industry') or data.get('knowsAbout'):
                        industry_data = data.get('industry') or data.get('knowsAbout')
                        if isinstance(industry_data, list):
                            info['industry'] = ', '.join(industry_data)
                        else:
                            info['industry'] = str(industry_data)
                            
            except Exception as e:
                logger.debug(f"Error parsing JSON-LD: {e}")
                continue
        
        return info
    
    def _extract_from_about_page(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract information from about page content"""
        info = {}
        
        # Get all text content
        text_content = soup.get_text().lower()
        
        # Look for founding year patterns
        year_patterns = [
            r'founded in (\d{4})',
            r'established in (\d{4})',
            r'since (\d{4})',
            r'started in (\d{4})',
            r'©\s*(\d{4})',
        ]
        
        for pattern in year_patterns:
            match = re.search(pattern, text_content)
            if match:
                year = int(match.group(1))
                if 1900 <= year <= 2024:  # Reasonable year range
                    info['company_year_est'] = str(year)
                    break
        
        # Look for company size indicators
        size_patterns = [
            (r'(\d+)[+\s]*employees', 'employees'),
            (r'team of (\d+)', 'employees'),
            (r'(\d+)[+\s]*people', 'employees'),
            (r'over (\d+) employees', 'employees'),
            (r'more than (\d+) employees', 'employees'),
        ]
        
        for pattern, unit in size_patterns:
            match = re.search(pattern, text_content)
            if match:
                size = int(match.group(1))
                if size < 10:
                    info['company_size'] = 'Startup (1-10)'
                elif size < 50:
                    info['company_size'] = 'Small (11-50)'
                elif size < 200:
                    info['company_size'] = 'Medium (51-200)'
                elif size < 1000:
                    info['company_size'] = 'Large (201-1000)'
                else:
                    info['company_size'] = 'Enterprise (1000+)'
                break
        
        return info
    
    def _find_about_page_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Find the about page URL"""
        about_keywords = ['about', 'about-us', 'company', 'who-we-are', 'our-story']
        
        # Look for links containing about keywords
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href'].lower()
            link_text = link.get_text().lower().strip()
            
            # Check if link text or href contains about keywords
            if any(keyword in href or keyword in link_text for keyword in about_keywords):
                if href.startswith('/'):
                    return urljoin(base_url, href)
                elif href.startswith('http'):
                    return href
        
        return None
    
    def _extract_industry_keywords(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract industry classification from page content"""
        info = {}
        
        # Get page title and description
        title = soup.find('title')
        title_text = title.get_text().lower() if title else ''
        
        description = soup.find('meta', attrs={'name': 'description'})
        desc_text = description.get('content', '').lower() if description else ''
        
        # Combine title and description
        content = f"{title_text} {desc_text}"
        
        # Industry classification keywords
        industry_keywords = {
            'Technology': ['software', 'tech', 'digital', 'app', 'platform', 'saas', 'ai', 'data', 'cloud'],
            'Healthcare': ['health', 'medical', 'hospital', 'clinic', 'pharma', 'wellness'],
            'Finance': ['finance', 'banking', 'investment', 'insurance', 'fintech', 'financial'],
            'E-commerce': ['ecommerce', 'e-commerce', 'online store', 'retail', 'marketplace'],
            'Manufacturing': ['manufacturing', 'production', 'factory', 'industrial'],
            'Consulting': ['consulting', 'advisory', 'services', 'strategy'],
            'Education': ['education', 'learning', 'training', 'school', 'university'],
            'Marketing': ['marketing', 'advertising', 'agency', 'digital marketing'],
            'Real Estate': ['real estate', 'property', 'housing'],
            'Food & Beverage': ['food', 'restaurant', 'catering', 'beverage'],
        }
        
        for industry, keywords in industry_keywords.items():
            if any(keyword in content for keyword in keywords):
                info['industry'] = industry
                break
        
        return info
    
    def _classify_industry_from_keywords(self, keywords: str) -> str:
        """Classify industry from meta keywords"""
        keywords = keywords.lower()
        
        if any(word in keywords for word in ['software', 'tech', 'digital', 'app']):
            return 'Technology'
        elif any(word in keywords for word in ['health', 'medical', 'wellness']):
            return 'Healthcare'
        elif any(word in keywords for word in ['finance', 'banking', 'investment']):
            return 'Finance'
        elif any(word in keywords for word in ['retail', 'ecommerce', 'shop']):
            return 'E-commerce'
        elif any(word in keywords for word in ['consulting', 'advisory', 'services']):
            return 'Consulting'
        
        return ''
    
    async def scrape_multiple_websites(self, websites: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
        """Scrape multiple websites concurrently"""
        throttler = Throttler(rate_limit=self.config.MAX_CONCURRENT_REQUESTS)
        
        async def scrape_single(session, website_url, company_name):
            async with throttler:
                try:
                    async with session.get(website_url, timeout=10) as response:
                        if response.status == 200:
                            content = await response.text()
                            soup = BeautifulSoup(content, 'html.parser')
                            
                            company_info = {
                                'website': website_url,
                                'company_name': company_name,
                                'company_size': '',
                                'industry': '',
                                'revenue_estimate': '',
                                'company_year_est': '',
                                'description': ''
                            }
                            
                            company_info.update(self._extract_from_meta_tags(soup))
                            company_info.update(self._extract_from_structured_data(soup))
                            company_info.update(self._extract_industry_keywords(soup))
                            
                            return company_info
                except Exception as e:
                    logger.error(f"Error scraping {website_url}: {e}")
                    return {'website': website_url, 'company_name': company_name, 'error': str(e)}
        
        async with aiohttp.ClientSession(headers=self.session.headers) as session:
            tasks = [scrape_single(session, url, name) for url, name in websites]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [r for r in results if isinstance(r, dict)]
    
    def get_company_info_with_selenium(self, website_url: str, company_name: str = "") -> Dict[str, Any]:
        """Use Selenium for JavaScript-heavy websites"""
        driver = None
        try:
            # Setup Chrome options
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"--user-agent={self.config.USER_AGENT}")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Setup driver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Navigate to website
            driver.get(website_url)
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source and parse
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            
            company_info = {
                'website': website_url,
                'company_size': '',
                'industry': '',
                'revenue_estimate': '',
                'company_year_est': '',
                'description': ''
            }
            
            company_info.update(self._extract_from_meta_tags(soup))
            company_info.update(self._extract_from_structured_data(soup))
            company_info.update(self._extract_industry_keywords(soup))
            
            return company_info
            
        except Exception as e:
            logger.error(f"Error with Selenium scraping {website_url}: {e}")
            return {}
        finally:
            if driver:
                driver.quit()
    
    def estimate_company_revenue(self, company_size: str, industry: str) -> str:
        """Estimate company revenue based on size and industry"""
        if not company_size:
            return ''
        
        # Revenue multipliers by industry
        industry_multipliers = {
            'Technology': 1.2,
            'Finance': 1.5,
            'Healthcare': 1.1,
            'Manufacturing': 0.9,
            'Consulting': 1.0,
            'E-commerce': 1.1,
            'default': 1.0
        }
        
        multiplier = industry_multipliers.get(industry, industry_multipliers['default'])
        
        # Base revenue estimates by company size
        if 'startup' in company_size.lower() or '1-10' in company_size:
            base_revenue = 500000  # $500K
        elif 'small' in company_size.lower() or '11-50' in company_size:
            base_revenue = 2000000  # $2M
        elif 'medium' in company_size.lower() or '51-200' in company_size:
            base_revenue = 10000000  # $10M
        elif 'large' in company_size.lower() or '201-1000' in company_size:
            base_revenue = 50000000  # $50M
        elif 'enterprise' in company_size.lower() or '1000+' in company_size:
            base_revenue = 200000000  # $200M
        else:
            return ''
        
        estimated_revenue = int(base_revenue * multiplier)
        
        # Format revenue in human-readable form
        if estimated_revenue >= 1000000000:
            return f"${estimated_revenue / 1000000000:.1f}B"
        elif estimated_revenue >= 1000000:
            return f"${estimated_revenue / 1000000:.1f}M"
        else:
            return f"${estimated_revenue / 1000:.0f}K"