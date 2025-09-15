import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import concurrent.futures
import time
from config import Config
from modules.odoo_client import OdooClient
from modules.sheets_client import GoogleSheetsClient
from modules.web_scraper import WebScraper
from modules.linkedin_enricher import LinkedInEnricher

logger = logging.getLogger(__name__)

class EnrichmentPipeline:
    """Main pipeline for lead enrichment"""
    
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.odoo_client = OdooClient(self.config)
        self.sheets_client = GoogleSheetsClient(self.config)
        self.web_scraper = WebScraper(self.config)
        self.linkedin_enricher = LinkedInEnricher(self.config)
        
        # Stats tracking
        self.stats = {
            'leads_extracted': 0,
            'leads_enriched': 0,
            'web_scraping_success': 0,
            'linkedin_enrichment_success': 0,
            'leads_updated_in_odoo': 0,
            'errors': []
        }
    
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Run the complete lead automation pipeline"""
        logger.info("Starting lead automation pipeline")
        start_time = time.time()
        
        try:
            # Step 1: Extract leads from Odoo
            logger.info("Step 1: Extracting unenriched leads from Odoo")
            if not await self._connect_odoo():
                raise RuntimeError("Failed to connect to Odoo")
            
            leads = self.odoo_client.get_unenriched_leads()
            if not leads:
                logger.info("No unenriched leads found")
                return self._get_pipeline_summary(start_time)
            
            self.stats['leads_extracted'] = len(leads)
            logger.info(f"Extracted {len(leads)} leads from Odoo")
            
            # Step 2: Setup Google Sheets
            logger.info("Step 2: Setting up Google Sheets")
            if not await self._setup_sheets():
                raise RuntimeError("Failed to setup Google Sheets")
            
            # Add leads to sheet
            if not self.sheets_client.add_leads_to_sheet(leads):
                logger.warning("Failed to add leads to sheet, continuing...")
            
            # Step 3: Enrich leads
            logger.info("Step 3: Starting lead enrichment")
            enriched_leads = await self._enrich_leads_batch(leads)
            
            # Step 4: Update sheet with enriched data
            logger.info("Step 4: Updating Google Sheets with enriched data")
            await self._update_sheet_with_enrichment(enriched_leads)
            
            # Step 5: Update Odoo with enriched data
            logger.info("Step 5: Updating Odoo with enriched data")
            await self._update_odoo_with_enrichment(enriched_leads)
            
            # Generate summary
            summary = self._get_pipeline_summary(start_time)
            logger.info(f"Pipeline completed successfully: {summary}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self.stats['errors'].append(str(e))
            return self._get_pipeline_summary(start_time, failed=True)
    
    async def _connect_odoo(self) -> bool:
        """Connect to Odoo"""
        try:
            return self.odoo_client.connect()
        except Exception as e:
            logger.error(f"Failed to connect to Odoo: {e}")
            return False
    
    async def _setup_sheets(self) -> bool:
        """Setup Google Sheets"""
        try:
            if not self.sheets_client.connect():
                return False
            
            if not self.sheets_client.get_or_create_spreadsheet():
                return False
            
            if not self.sheets_client.get_or_create_worksheet():
                return False
            
            return self.sheets_client.initialize_sheet()
            
        except Exception as e:
            logger.error(f"Failed to setup Google Sheets: {e}")
            return False
    
    async def _enrich_leads_batch(self, leads: List[Dict[str, Any]], progress_callback=None) -> List[Dict[str, Any]]:
        """Enrich leads in batches with progress updates"""
        enriched_leads = []
        batch_size = min(self.config.BATCH_SIZE, 5)  # Smaller batches for better progress
        total_batches = (len(leads) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(leads), batch_size):
            batch = leads[batch_idx:batch_idx + batch_size]
            current_batch_num = batch_idx // batch_size + 1
            
            logger.info(f"Processing batch {current_batch_num}/{total_batches} ({len(batch)} leads)")
            
            if progress_callback:
                progress = (current_batch_num - 1) * 100 / total_batches
                await progress_callback(progress, f"Processing batch {current_batch_num}/{total_batches}")
            
            batch_enriched = await self._enrich_leads_parallel(batch)
            enriched_leads.extend(batch_enriched)
            
            # Shorter delay between batches
            if batch_idx + batch_size < len(leads):
                await asyncio.sleep(0.5)
        
        return enriched_leads
    
    async def _enrich_leads_parallel(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enrich leads in parallel with timeout"""
        tasks = []
        
        for lead in leads:
            # Add timeout to individual lead enrichment (2 minutes per lead)
            task = asyncio.create_task(
                asyncio.wait_for(self._enrich_single_lead(lead), timeout=120)
            )
            tasks.append(task)
        
        enriched_leads = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        valid_leads = []
        for i, result in enumerate(enriched_leads):
            if isinstance(result, Exception):
                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(f"Timeout enriching lead {i}: {leads[i].get('Full Name', 'Unknown')}")
                    leads[i]['enrichment_status'] = 'timeout'
                    leads[i]['Enriched'] = 'Timeout'
                else:
                    logger.error(f"Error enriching lead {i}: {result}")
                    leads[i]['enrichment_status'] = 'failed'
                    leads[i]['Enriched'] = 'Failed'
                
                self.stats['errors'].append(f"Lead enrichment error: {result}")
                valid_leads.append(leads[i])
            else:
                valid_leads.append(result)
        
        return valid_leads
    
    async def _enrich_single_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single lead with all available data"""
        enriched_lead = lead.copy()
        enrichment_sources = []
        
        try:
            # 1. Web scraping enrichment - try website first, then extract from email
            website = lead.get('website', '').strip()
            
            # If no website, try to extract domain from email
            if not website:
                email = lead.get('email') or lead.get('email_from', '')
                if email and '@' in email:
                    domain = email.split('@')[1].lower()
                    # Skip common email providers
                    if domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'aol.com']:
                        website = f"https://{domain}"
                        logger.info(f"Extracted website from email: {website}")
            
            if website:
                logger.debug(f"Web scraping for {lead.get('Company Name', '')} at {website}")
                web_info = self.web_scraper.get_company_info_from_website(
                    website, 
                    lead.get('Company Name', '')
                )
                
                if web_info:
                    self._merge_web_scraping_data(enriched_lead, web_info)
                    enrichment_sources.append('web')
                    self.stats['web_scraping_success'] += 1
                    logger.info(f"Web scraping successful for {website}")
                else:
                    logger.debug(f"Web scraping returned no data for {website}")
            
            # 2. LinkedIn enrichment - Always try both direct scraping and search
            linkedin_url = lead.get('LinkedIn Link', '').strip()
            if linkedin_url:
                logger.debug(f"LinkedIn enrichment for {lead.get('Full Name', '')}")
                linkedin_info = self.linkedin_enricher.enrich_linkedin_profile(linkedin_url)
                
                if linkedin_info:
                    self._merge_linkedin_data(enriched_lead, linkedin_info)
                    enrichment_sources.append('linkedin')
                    self.stats['linkedin_enrichment_success'] += 1
            
            # Always try searching for LinkedIn profile, even if we had a direct link
            full_name = lead.get('Full Name', '').strip()
            company_name = lead.get('Company Name', '').strip()
            
            if full_name and 'linkedin' not in enrichment_sources:
                logger.debug(f"Searching LinkedIn for {full_name}")
                linkedin_info = await self.linkedin_enricher.search_linkedin_profile(full_name, company_name)
                
                if linkedin_info:
                    self._merge_linkedin_data(enriched_lead, linkedin_info)
                    enrichment_sources.append('linkedin_search')
                    self.stats['linkedin_enrichment_success'] += 1
            
            # 3. Person-specific web search (aggressive approach - always try)
            logger.debug(f"Searching web for person info: {lead.get('Full Name', '')}")
            person_info = await self.web_scraper.search_person_info(
                lead.get('Full Name', ''),
                lead.get('Company Name', ''),
                lead.get('email') or lead.get('email_from', '')
            )
            
            if person_info:
                self._merge_person_search_data(enriched_lead, person_info)
                if 'person_search' not in enrichment_sources:
                    enrichment_sources.append('person_search')
                
                # If web search found LinkedIn URL and we didn't scrape it yet, try it
                if person_info.get('linkedin_url') and 'linkedin' not in enrichment_sources and 'linkedin_search' not in enrichment_sources:
                    logger.debug(f"Found LinkedIn URL in web search, scraping: {person_info['linkedin_url']}")
                    linkedin_from_search = self.linkedin_enricher.enrich_linkedin_profile(person_info['linkedin_url'])
                    if linkedin_from_search:
                        self._merge_linkedin_data(enriched_lead, linkedin_from_search)
                        enrichment_sources.append('linkedin_from_search')
                        self.stats['linkedin_enrichment_success'] += 1
            
            # 4. Additional data processing
            self._calculate_quality_score(enriched_lead)
            self._estimate_revenue_if_missing(enriched_lead)
            
            # Mark as enriched if we got any data
            if enrichment_sources:
                enriched_lead['Enriched'] = 'Yes'
                enriched_lead['enrichment_sources'] = ', '.join(enrichment_sources)
                self.stats['leads_enriched'] += 1
                logger.info(f"Successfully enriched {lead.get('Full Name', '')} with sources: {', '.join(enrichment_sources)}")
            else:
                enriched_lead['Enriched'] = 'Partial'
                enriched_lead['enrichment_sources'] = 'none'
                logger.warning(f"No enrichment data found for {lead.get('Full Name', '')}")
            
            enriched_lead['enrichment_date'] = datetime.now().isoformat()
            
            return enriched_lead
            
        except Exception as e:
            logger.error(f"Error enriching lead {lead.get('Full Name', '')}: {e}")
            enriched_lead['Enriched'] = 'Failed'
            enriched_lead['enrichment_error'] = str(e)
            return enriched_lead
    
    def _merge_person_search_data(self, lead: Dict[str, Any], person_info: Dict[str, Any]):
        """Merge person search data into lead"""
        try:
            # Update job title if found and not already set
            if person_info.get('job_title') and not lead.get('Job Role'):
                lead['Job Role'] = person_info['job_title'].title()
            
            # Update industry if found and not already set  
            if person_info.get('industry_hint') and not lead.get('Industry'):
                lead['Industry'] = person_info['industry_hint'].title()
            
            # Update LinkedIn URL if found and not already set
            if person_info.get('linkedin_url') and not lead.get('LinkedIn Link'):
                lead['LinkedIn Link'] = person_info['linkedin_url']
            
            # If company was confirmed in search, this adds confidence
            if person_info.get('company_confirmed'):
                lead['company_search_confirmed'] = True
            
            # Add any other relevant info found
            if person_info.get('company_name') and not lead.get('Company Name'):
                lead['Company Name'] = person_info['company_name']
                
            logger.info(f"Merged person search data: job_title={person_info.get('job_title')}, industry={person_info.get('industry_hint')}, linkedin={person_info.get('linkedin_url')}")
            
        except Exception as e:
            logger.error(f"Error merging person search data: {e}")
    
    def _merge_web_scraping_data(self, lead: Dict[str, Any], web_info: Dict[str, Any]):
        """Merge web scraping data into lead"""
        mapping = {
            'company_size': 'Company Size',
            'industry': 'Industry',
            'revenue_estimate': 'Company Revenue Estimated',
            'company_year_est': 'Company year EST'
        }
        
        for web_key, lead_key in mapping.items():
            if web_info.get(web_key) and not lead.get(lead_key):
                lead[lead_key] = web_info[web_key]
    
    def _merge_linkedin_data(self, lead: Dict[str, Any], linkedin_info: Dict[str, Any]):
        """Merge LinkedIn data into lead"""
        # Update LinkedIn URL if found
        if linkedin_info.get('linkedin_url') and not lead.get('LinkedIn Link'):
            lead['LinkedIn Link'] = linkedin_info['linkedin_url']
        
        # Update job title - prefer LinkedIn data as it's more accurate
        if linkedin_info.get('job_title'):
            if not lead.get('Job Role') or len(linkedin_info['job_title']) > len(lead.get('Job Role', '')):
                lead['Job Role'] = linkedin_info['job_title']
        
        # Update company name if more detailed
        if linkedin_info.get('company_name'):
            if not lead.get('Company Name') or len(linkedin_info['company_name']) > len(lead.get('Company Name', '')):
                lead['Company Name'] = linkedin_info['company_name']
        
        # Update industry - prefer LinkedIn data
        if linkedin_info.get('industry') and not lead.get('Industry'):
            lead['Industry'] = linkedin_info['industry']
        
        # Update full name if more complete
        if linkedin_info.get('full_name') and len(linkedin_info['full_name']) > len(lead.get('Full Name', '')):
            lead['Full Name'] = linkedin_info['full_name']
        
        # Additional LinkedIn-specific data
        if linkedin_info.get('connections'):
            lead['linkedin_connections'] = linkedin_info['connections']
        if linkedin_info.get('location'):
            lead['linkedin_location'] = linkedin_info['location']
        if linkedin_info.get('about'):
            lead['linkedin_about'] = linkedin_info['about'][:200]  # Truncate to avoid too much data
    
    def _calculate_quality_score(self, lead: Dict[str, Any]):
        """Calculate quality score based on available data"""
        score = 0
        max_score = 5
        
        # Check data completeness
        if lead.get('Full Name'): score += 0.5
        if lead.get('Company Name'): score += 0.5
        if lead.get('LinkedIn Link'): score += 1
        if lead.get('Job Role'): score += 0.5
        if lead.get('Industry'): score += 0.5
        if lead.get('Company Size'): score += 0.5
        if lead.get('Phone'): score += 0.5
        if lead.get('Company Revenue Estimated'): score += 0.5
        if lead.get('Company year EST'): score += 0.5
        
        # Bonus for enrichment sources
        if lead.get('enrichment_sources'):
            sources = lead['enrichment_sources'].split(', ')
            if 'linkedin' in sources: score += 0.5
            if 'web' in sources: score += 0.5
        
        # Cap at max score and round
        final_score = min(score, max_score)
        lead['Quality (Out of 5)'] = str(int(round(final_score)))
    
    def _estimate_revenue_if_missing(self, lead: Dict[str, Any]):
        """Estimate revenue if missing"""
        if not lead.get('Company Revenue Estimated') and lead.get('Company Size') and lead.get('Industry'):
            estimated_revenue = self.web_scraper.estimate_company_revenue(
                lead['Company Size'], 
                lead['Industry']
            )
            if estimated_revenue:
                lead['Company Revenue Estimated'] = estimated_revenue
    
    async def _update_sheet_with_enrichment(self, enriched_leads: List[Dict[str, Any]]):
        """Update Google Sheets with enriched data"""
        try:
            # Clear existing data and add enriched data
            self.sheets_client.worksheet.clear()
            self.sheets_client.initialize_sheet()
            
            if not self.sheets_client.add_leads_to_sheet(enriched_leads):
                logger.error("Failed to update sheet with enriched data")
            
            logger.info(f"Updated Google Sheets with {len(enriched_leads)} enriched leads")
            
        except Exception as e:
            logger.error(f"Error updating sheet: {e}")
            self.stats['errors'].append(f"Sheet update error: {e}")
    
    async def _update_odoo_with_enrichment(self, enriched_leads: List[Dict[str, Any]]):
        """Update Odoo with enriched data"""
        try:
            updates = []
            
            for lead in enriched_leads:
                lead_id = lead.get('id')
                if not lead_id:
                    continue
                
                # Prepare update values
                update_values = {}
                if lead.get('Quality (Out of 5)'):
                    update_values['Quality (Out of 5)'] = lead['Quality (Out of 5)']
                
                if update_values:
                    updates.append((lead_id, update_values))
            
            if updates:
                success_count = self.odoo_client.bulk_update_leads(updates)
                self.stats['leads_updated_in_odoo'] = success_count
                logger.info(f"Updated {success_count} leads in Odoo")
            
        except Exception as e:
            logger.error(f"Error updating Odoo: {e}")
            self.stats['errors'].append(f"Odoo update error: {e}")
    
    def _get_pipeline_summary(self, start_time: float, failed: bool = False) -> Dict[str, Any]:
        """Generate pipeline execution summary"""
        end_time = time.time()
        duration = end_time - start_time
        
        summary = {
            'status': 'failed' if failed else 'completed',
            'duration_seconds': round(duration, 2),
            'timestamp': datetime.now().isoformat(),
            'stats': self.stats.copy(),
            'config': {
                'salesperson': self.config.SALESPERSON_NAME,
                'batch_size': self.config.BATCH_SIZE,
                'max_concurrent': self.config.MAX_CONCURRENT_REQUESTS
            }
        }
        
        # Add spreadsheet URL if available
        if self.sheets_client.spreadsheet:
            summary['spreadsheet_url'] = self.sheets_client.spreadsheet_url
        
        return summary
    
    async def enrich_specific_leads(self, lead_ids: List[int]) -> Dict[str, Any]:
        """Enrich only specific leads by ID"""
        logger.info(f"Enriching specific leads: {lead_ids}")
        
        try:
            if not await self._connect_odoo():
                raise RuntimeError("Failed to connect to Odoo")
            
            # Get specific leads from Odoo
            all_leads = self.odoo_client.get_unenriched_leads()
            specific_leads = [lead for lead in all_leads if lead.get('id') in lead_ids]
            
            if not specific_leads:
                return {'status': 'no_leads_found', 'message': f'No leads found for IDs: {lead_ids}'}
            
            # Enrich the specific leads
            enriched_leads = await self._enrich_leads_batch(specific_leads)
            
            # Update Odoo
            await self._update_odoo_with_enrichment(enriched_leads)
            
            return {
                'status': 'completed',
                'processed_leads': len(enriched_leads),
                'stats': self.stats
            }
            
        except Exception as e:
            logger.error(f"Error enriching specific leads: {e}")
            return {'status': 'failed', 'error': str(e)}