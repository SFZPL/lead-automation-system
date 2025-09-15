import asyncio
import aiohttp
import time
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs
import re
import json
import logging
from apify_client import ApifyClient
from config import Config

logger = logging.getLogger(__name__)

class LinkedInEnricher:
    """LinkedIn enrichment using Apify API"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.apify_client = None
        if self.config.APIFY_API_TOKEN:
            self.apify_client = ApifyClient(self.config.APIFY_API_TOKEN)
    
    def enrich_linkedin_profile(self, linkedin_url: str) -> Dict[str, Any]:
        """Enrich data from LinkedIn profile URL"""
        if not self.apify_client:
            logger.warning("Apify client not configured - LinkedIn enrichment disabled")
            return {}
        
        try:
            if not linkedin_url or 'linkedin.com' not in linkedin_url:
                return {}
            
            # Clean the LinkedIn URL
            clean_url = self._clean_linkedin_url(linkedin_url)
            if not clean_url:
                return {}
            
            # Extract username from LinkedIn URL for your specific actor
            username = self._extract_linkedin_username(clean_url)
            if not username:
                logger.warning(f"Could not extract username from LinkedIn URL: {clean_url}")
                return {}
            
            # Use your specific LinkedIn actor
            run_input = {
                "username": username,
                "includeEmail": False,
            }
            
            # Start the scraping run with your actor ID
            run = self.apify_client.actor("VhxlqXRwhW8H5hNV").call(
                run_input=run_input
            )
            
            # Get results
            items = []
            for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            
            if items:
                profile_data = items[0]
                return self._process_linkedin_data(profile_data)
            
            return {}
            
        except Exception as e:
            logger.error(f"Error enriching LinkedIn profile {linkedin_url}: {e}")
            return {}
    
    def enrich_company_from_linkedin(self, company_linkedin_url: str) -> Dict[str, Any]:
        """Enrich company data from LinkedIn company page"""
        if not self.apify_client:
            logger.warning("Apify client not configured - LinkedIn company enrichment disabled")
            return {}
        
        try:
            if not company_linkedin_url or 'linkedin.com/company' not in company_linkedin_url:
                return {}
            
            # Use Apify's LinkedIn company scraper
            run_input = {
                "companyUrls": [company_linkedin_url],
                "proxyConfiguration": {
                    "useApifyProxy": True
                }
            }
            
            run = self.apify_client.actor("apify/linkedin-company-scraper").call(
                run_input=run_input
            )
            
            items = []
            for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            
            if items:
                company_data = items[0]
                return self._process_company_data(company_data)
            
            return {}
            
        except Exception as e:
            logger.error(f"Error enriching LinkedIn company {company_linkedin_url}: {e}")
            return {}
    
    async def search_linkedin_profile(self, full_name: str, company_name: str = "") -> Dict[str, Any]:
        """Search for LinkedIn profile by name and company using web search with parallel requests"""
        try:
            import aiohttp
            import re
            import urllib.parse
            from bs4 import BeautifulSoup
            
            # Construct comprehensive search queries
            search_queries = [
                f'"{full_name}" {company_name} site:linkedin.com/in',
                f'{full_name} {company_name} linkedin',
                f'"{full_name}" linkedin profile',
                f'{full_name} site:linkedin.com'
            ]
            
            # Remove empty company name from queries if not provided
            if not company_name:
                search_queries = [
                    f'"{full_name}" site:linkedin.com/in', 
                    f'{full_name} linkedin profile',
                    f'"{full_name}" linkedin'
                ]
            
            # Search all engines in parallel for each query
            for query in search_queries:
                logger.info(f"Searching for LinkedIn profile: {query}")
                
                linkedin_urls = await self._search_linkedin_parallel(query)
                
                # Deduplicate URLs and validate them
                unique_urls = list(set(linkedin_urls))
                valid_urls = [url for url in unique_urls if self.validate_linkedin_url(url)]
                
                # Try to enrich each valid URL
                for linkedin_url in valid_urls[:3]:  # Try up to 3 URLs per query
                    logger.info(f"Found potential LinkedIn profile: {linkedin_url}")
                    try:
                        profile_data = self.enrich_linkedin_profile(linkedin_url)
                        if profile_data:
                            logger.info(f"Successfully enriched LinkedIn profile: {linkedin_url}")
                            profile_data['linkedin_url'] = linkedin_url  # Ensure URL is included
                            return profile_data
                    except Exception as e:
                        logger.debug(f"Failed to enrich LinkedIn profile {linkedin_url}: {e}")
                        continue
                
                # Small delay between queries to be respectful
                await asyncio.sleep(0.3)
            
            logger.info(f"No LinkedIn profile found for {full_name}")
            return {}
            
        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
            return {}
        except Exception as e:
            logger.error(f"Error searching LinkedIn for {full_name}: {e}")
            return {}

    async def _search_linkedin_parallel(self, query: str) -> List[str]:
        """Search for LinkedIn URLs using multiple search engines in parallel"""
        import urllib.parse
        import re
        
        # Define search engines including Google
        search_engines = [
            ("DuckDuckGo", f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"),
            ("Bing", f"https://www.bing.com/search?q={urllib.parse.quote(query)}"),
            ("Google", f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async def search_single_engine(session, engine_name, search_url):
            """Search a single engine for LinkedIn URLs"""
            try:
                logger.debug(f"Searching {engine_name} for LinkedIn URLs: {query}")
                
                # Add throttling between requests to avoid being blocked
                await asyncio.sleep(0.1 * hash(engine_name) % 3)  # Stagger requests
                
                async with session.get(search_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Search for LinkedIn URLs in response text
                        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-_]+)/?'
                        matches = re.findall(linkedin_pattern, content, re.IGNORECASE)
                        
                        linkedin_urls = []
                        for match in matches[:5]:  # Top 5 matches per engine
                            url = f"https://www.linkedin.com/in/{match}"
                            linkedin_urls.append(url)
                        
                        # Also try BeautifulSoup parsing for better results
                        try:
                            soup = BeautifulSoup(content, 'html.parser')
                            all_text = soup.get_text()
                            additional_matches = re.findall(linkedin_pattern, all_text, re.IGNORECASE)
                            
                            for match in additional_matches[:3]:
                                url = f"https://www.linkedin.com/in/{match}"
                                if url not in linkedin_urls:
                                    linkedin_urls.append(url)
                                    
                        except Exception as e:
                            logger.debug(f"BeautifulSoup parsing failed for {engine_name}: {e}")
                        
                        if linkedin_urls:
                            logger.info(f"Found {len(linkedin_urls)} LinkedIn URLs from {engine_name}")
                        
                        return linkedin_urls
                    else:
                        logger.debug(f"{engine_name} returned status {response.status}")
                        return []
                        
            except Exception as e:
                logger.debug(f"{engine_name} search failed: {e}")
                return []
        
        # Execute all searches concurrently
        linkedin_urls = []
        try:
            async with aiohttp.ClientSession() as session:
                tasks = [search_single_engine(session, engine_name, search_url) 
                        for engine_name, search_url in search_engines]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Combine all URLs from all engines
                for result in results:
                    if isinstance(result, list):
                        linkedin_urls.extend(result)
                        
        except Exception as e:
            logger.error(f"Error in parallel LinkedIn search: {e}")
        
        return linkedin_urls
    
    def _extract_linkedin_url(self, search_result_url: str) -> Optional[str]:
        """Extract clean LinkedIn URL from search result"""
        import re
        
        # Handle DuckDuckGo redirect URLs
        if 'duckduckgo.com' in search_result_url:
            # Extract the actual URL from DuckDuckGo redirect
            import urllib.parse
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(search_result_url).query)
            if 'uddg' in parsed:
                actual_url = urllib.parse.unquote(parsed['uddg'][0])
            else:
                return None
        else:
            actual_url = search_result_url
        
        # Extract LinkedIn profile URL pattern
        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-]+)'
        match = re.search(linkedin_pattern, actual_url)
        
        if match:
            return f"https://www.linkedin.com/in/{match.group(1)}"
        return None
    
    def _clean_linkedin_url(self, url: str) -> Optional[str]:
        """Clean and validate LinkedIn URL"""
        try:
            if not url:
                return None
            
            # Remove any HTML tags if present
            url = re.sub(r'<[^>]+>', '', url)
            
            # Extract URL if it's in text
            url_match = re.search(r'https?://[^\s<>"\']+', url)
            if url_match:
                url = url_match.group()
            
            # Ensure it's a LinkedIn URL
            if 'linkedin.com' not in url.lower():
                return None
            
            # Clean up the URL
            parsed = urlparse(url)
            if parsed.netloc and 'linkedin.com' in parsed.netloc.lower():
                # Reconstruct clean URL
                clean_url = f"https://www.linkedin.com{parsed.path}"
                return clean_url
            
            return None
            
        except Exception as e:
            logger.error(f"Error cleaning LinkedIn URL {url}: {e}")
            return None
    
    def _process_linkedin_data(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process LinkedIn profile data"""
        try:
            processed = {
                'linkedin_url': profile_data.get('profileUrl', ''),
                'full_name': profile_data.get('fullName', ''),
                'job_title': profile_data.get('headline', ''),
                'company_name': '',
                'industry': profile_data.get('industry', ''),
                'location': profile_data.get('location', ''),
                'connections': profile_data.get('connectionsCount', ''),
                'about': profile_data.get('about', ''),
            }
            
            # Extract current company from experience
            experience = profile_data.get('experience', [])
            if experience and len(experience) > 0:
                current_job = experience[0]  # Most recent job
                processed['company_name'] = current_job.get('companyName', '')
                processed['job_title'] = current_job.get('title', processed['job_title'])
            
            # Extract education
            education = profile_data.get('education', [])
            if education:
                processed['education'] = [
                    {
                        'school': edu.get('schoolName', ''),
                        'degree': edu.get('degreeName', ''),
                        'field': edu.get('fieldOfStudy', '')
                    }
                    for edu in education[:3]  # Top 3 education entries
                ]
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing LinkedIn data: {e}")
            return {}
    
    def _process_company_data(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process LinkedIn company data"""
        try:
            processed = {
                'company_name': company_data.get('name', ''),
                'industry': company_data.get('industry', ''),
                'company_size': self._format_company_size(company_data.get('employeeCount', '')),
                'company_linkedin_url': company_data.get('url', ''),
                'headquarters': company_data.get('headquarters', ''),
                'founded': company_data.get('founded', ''),
                'specialties': company_data.get('specialties', []),
                'description': company_data.get('description', ''),
                'website': company_data.get('website', ''),
                'follower_count': company_data.get('followerCount', ''),
            }
            
            return processed
            
        except Exception as e:
            logger.error(f"Error processing company data: {e}")
            return {}
    
    def _format_company_size(self, employee_count: str) -> str:
        """Format company size from LinkedIn data"""
        if not employee_count:
            return ''
        
        try:
            # Extract numbers from employee count string
            numbers = re.findall(r'\d+', str(employee_count))
            if not numbers:
                return employee_count
            
            count = int(numbers[0])
            
            if count <= 10:
                return 'Startup (1-10)'
            elif count <= 50:
                return 'Small (11-50)'
            elif count <= 200:
                return 'Medium (51-200)'
            elif count <= 1000:
                return 'Large (201-1000)'
            else:
                return 'Enterprise (1000+)'
                
        except Exception:
            return employee_count
    
    def _find_best_match(self, search_results: List[Dict], target_name: str, target_company: str = "") -> Optional[Dict]:
        """Find best matching profile from search results"""
        if not search_results:
            return None
        
        target_name_lower = target_name.lower()
        target_company_lower = target_company.lower() if target_company else ""
        
        best_match = None
        best_score = 0
        
        for result in search_results:
            score = 0
            
            # Name matching
            result_name = result.get('fullName', '').lower()
            if target_name_lower in result_name or result_name in target_name_lower:
                score += 3
            
            # Company matching
            if target_company_lower:
                result_company = result.get('companyName', '').lower()
                if target_company_lower in result_company or result_company in target_company_lower:
                    score += 2
            
            # Position matching (if available)
            headline = result.get('headline', '').lower()
            if any(word in headline for word in target_name_lower.split()):
                score += 1
            
            if score > best_score:
                best_score = score
                best_match = result
        
        return best_match if best_score >= 2 else None
    
    async def bulk_enrich_profiles(self, profiles: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Bulk enrich multiple LinkedIn profiles"""
        if not self.apify_client:
            logger.warning("Apify client not configured - bulk enrichment disabled")
            return []
        
        results = []
        
        # Process in batches to avoid rate limits
        batch_size = 10
        for i in range(0, len(profiles), batch_size):
            batch = profiles[i:i + batch_size]
            
            # Process batch
            batch_results = []
            for profile in batch:
                linkedin_url = profile.get('linkedin_url', '')
                if linkedin_url:
                    enriched = self.enrich_linkedin_profile(linkedin_url)
                else:
                    # Try searching by name and company
                    full_name = profile.get('full_name', '')
                    company_name = profile.get('company_name', '')
                    enriched = self.search_linkedin_profile(full_name, company_name)
                
                batch_results.append({
                    'original': profile,
                    'enriched': enriched
                })
            
            results.extend(batch_results)
            
            # Rate limiting - wait between batches
            if i + batch_size < len(profiles):
                await asyncio.sleep(2)
        
        return results
    
    def validate_linkedin_url(self, url: str) -> bool:
        """Validate if URL is a proper LinkedIn profile URL"""
        try:
            if not url:
                return False
            
            clean_url = self._clean_linkedin_url(url)
            return bool(clean_url and '/in/' in clean_url)
            
        except Exception:
            return False
    
    def extract_company_from_linkedin_url(self, linkedin_url: str) -> str:
        """Extract company name from LinkedIn URL if it's a company page"""
        try:
            if 'linkedin.com/company/' in linkedin_url:
                parsed = urlparse(linkedin_url)
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2 and path_parts[0] == 'company':
                    return path_parts[1].replace('-', ' ').title()
            return ''
        except Exception:
            return ''
    
    def _extract_linkedin_username(self, linkedin_url: str) -> Optional[str]:
        """Extract LinkedIn username from profile URL"""
        try:
            if not linkedin_url or 'linkedin.com' not in linkedin_url:
                return None
            
            # Handle different LinkedIn URL formats
            # https://linkedin.com/in/username
            # https://www.linkedin.com/in/username/
            # https://linkedin.com/in/username?param=value
            
            parsed = urlparse(linkedin_url)
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) >= 2 and path_parts[0] == 'in':
                username = path_parts[1]
                # Remove any trailing parameters or special characters
                username = re.sub(r'[^a-zA-Z0-9\-_].*$', '', username)
                return username if username else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting username from LinkedIn URL {linkedin_url}: {e}")
            return None