import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional
from config import Config

def setup_logging(config: Config = None, log_level: str = "INFO") -> logging.Logger:
    """Setup comprehensive logging for the lead automation system"""
    
    config = config or Config()
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    logger.addHandler(console_handler)
    
    # File handler - main log
    main_log_file = os.path.join(logs_dir, 'lead_automation.log')
    file_handler = logging.handlers.RotatingFileHandler(
        main_log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Error file handler
    error_log_file = os.path.join(logs_dir, 'errors.log')
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    logger.addHandler(error_handler)
    
    # Daily log file handler
    daily_log_file = os.path.join(logs_dir, f'daily_{datetime.now().strftime("%Y%m%d")}.log')
    daily_handler = logging.FileHandler(daily_log_file)
    daily_handler.setLevel(logging.INFO)
    daily_handler.setFormatter(detailed_formatter)
    logger.addHandler(daily_handler)
    
    # Configure third-party loggers
    configure_third_party_loggers()
    
    logger.info("Logging system initialized")
    return logger

def configure_third_party_loggers():
    """Configure logging levels for third-party libraries"""
    
    # Reduce noise from third-party libraries
    third_party_loggers = [
        'urllib3.connectionpool',
        'requests.packages.urllib3.connectionpool',
        'selenium.webdriver.remote.remote_connection',
        'apify_client',
        'gspread',
        'google.auth',
        'aiohttp.access',
        'asyncio'
    ]
    
    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

def get_module_logger(module_name: str) -> logging.Logger:
    """Get a logger for a specific module"""
    return logging.getLogger(module_name)

class LoggingMixin:
    """Mixin class to add logging capabilities to other classes"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger
    
    def log_method_entry(self, method_name: str, **kwargs):
        """Log method entry with parameters"""
        params = ', '.join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.debug(f"Entering {method_name}({params})")
    
    def log_method_exit(self, method_name: str, result=None):
        """Log method exit with result"""
        if result is not None:
            self.logger.debug(f"Exiting {method_name} with result: {type(result).__name__}")
        else:
            self.logger.debug(f"Exiting {method_name}")
    
    def log_error(self, error: Exception, context: str = ""):
        """Log error with context"""
        context_str = f" in {context}" if context else ""
        self.logger.error(f"{type(error).__name__}{context_str}: {str(error)}", exc_info=True)
    
    def log_performance(self, operation: str, duration: float, **metrics):
        """Log performance metrics"""
        metrics_str = ', '.join(f"{k}={v}" for k, v in metrics.items())
        self.logger.info(f"Performance - {operation}: {duration:.2f}s, {metrics_str}")

def log_pipeline_stats(stats: dict, logger: Optional[logging.Logger] = None):
    """Log pipeline execution statistics"""
    if logger is None:
        logger = logging.getLogger('pipeline_stats')
    
    logger.info("=== Pipeline Execution Statistics ===")
    logger.info(f"Leads extracted: {stats.get('leads_extracted', 0)}")
    logger.info(f"Leads enriched: {stats.get('leads_enriched', 0)}")
    logger.info(f"Web scraping successes: {stats.get('web_scraping_success', 0)}")
    logger.info(f"LinkedIn enrichment successes: {stats.get('linkedin_enrichment_success', 0)}")
    logger.info(f"Leads updated in Odoo: {stats.get('leads_updated_in_odoo', 0)}")
    
    errors = stats.get('errors', [])
    if errors:
        logger.warning(f"Errors encountered: {len(errors)}")
        for i, error in enumerate(errors[:5], 1):  # Log first 5 errors
            logger.warning(f"Error {i}: {error}")
        if len(errors) > 5:
            logger.warning(f"... and {len(errors) - 5} more errors")
    else:
        logger.info("No errors encountered")
    
    logger.info("=====================================")

class PerformanceLogger:
    """Context manager for logging performance metrics"""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None, **context):
        self.operation = operation
        self.logger = logger or logging.getLogger('performance')
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Starting {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            
            if exc_type is None:
                level = logging.INFO
                status = "completed"
            else:
                level = logging.ERROR
                status = "failed"
                self.context['error'] = str(exc_val)
            
            context_str = ', '.join(f"{k}={v}" for k, v in self.context.items())
            self.logger.log(level, f"{self.operation} {status} in {duration:.2f}s - {context_str}")

def log_api_request(url: str, method: str = "GET", status_code: int = None, 
                   duration: float = None, logger: Optional[logging.Logger] = None):
    """Log API request details"""
    if logger is None:
        logger = logging.getLogger('api_requests')
    
    message = f"{method} {url}"
    
    if status_code is not None:
        message += f" - Status: {status_code}"
    
    if duration is not None:
        message += f" - Duration: {duration:.2f}s"
    
    if status_code and 200 <= status_code < 300:
        logger.info(message)
    elif status_code and status_code >= 400:
        logger.warning(message)
    else:
        logger.debug(message)

def log_data_quality_check(lead_data: dict, logger: Optional[logging.Logger] = None):
    """Log data quality assessment for a lead"""
    if logger is None:
        logger = logging.getLogger('data_quality')
    
    required_fields = ['Full Name', 'Company Name']
    optional_fields = ['LinkedIn Link', 'Job Role', 'Industry', 'Company Size', 'Phone']
    
    missing_required = [field for field in required_fields if not lead_data.get(field)]
    missing_optional = [field for field in optional_fields if not lead_data.get(field)]
    
    completeness = ((len(required_fields + optional_fields) - len(missing_required + missing_optional)) 
                   / len(required_fields + optional_fields)) * 100
    
    if missing_required:
        logger.warning(f"Lead {lead_data.get('Full Name', 'Unknown')} missing required fields: {missing_required}")
    
    logger.debug(f"Lead {lead_data.get('Full Name', 'Unknown')} completeness: {completeness:.1f}%")
    
    if missing_optional:
        logger.debug(f"Missing optional fields: {missing_optional}")
    
    return completeness

def create_audit_log(action: str, details: dict, logger: Optional[logging.Logger] = None):
    """Create audit log entry"""
    if logger is None:
        logger = logging.getLogger('audit')
    
    audit_entry = {
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'details': details
    }
    
    logger.info(f"AUDIT: {action} - {details}")