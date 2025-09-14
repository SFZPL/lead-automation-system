# Lead Automation System v2.0 🚀

A modern, comprehensive lead automation system with a sleek web interface that extracts leads from Odoo, enriches them with web scraping and LinkedIn data, manages them in Google Sheets, and updates Odoo with the enriched information.

## ✨ Features

### 🖥️ **Modern Web Interface**
- **Beautiful Dashboard**: Intuitive dashboard with real-time statistics
- **One-Click Operations**: Extract leads, enrich data, and run full pipeline with single clicks
- **Real-Time Progress**: Live progress tracking with WebSocket updates
- **Lead Management**: Interactive table to view and manage all leads
- **Configuration UI**: Easy-to-use settings management

### 🔧 **Core Automation**
- **Odoo Integration**: Extract unenriched leads from Odoo CRM
- **Google Sheets Management**: Create and manage leads in Google Sheets with proper formatting
- **Web Scraping**: Extract company information from websites
- **LinkedIn Enrichment**: Enrich leads using Apify's LinkedIn scrapers
- **Data Quality**: Calculate quality scores based on data completeness
- **Batch Processing**: Process leads in configurable batches
- **Error Handling**: Comprehensive error handling and logging
- **Audit Trail**: Complete audit logging for all operations

### 🌐 **Technical Stack**
- **Backend**: FastAPI with async operations
- **Frontend**: React with TypeScript and Tailwind CSS
- **Real-time**: WebSocket connections for live updates
- **Database**: SQLite for local operations
- **Security**: Environment-based configuration

## System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│                 │    │                  │    │                 │
│      Odoo       │◄──►│  Lead Automation │◄──►│  Google Sheets  │
│      CRM        │    │     System       │    │                 │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌──────────────────────┐
                    │                      │
                    │   Enrichment APIs    │
                    │                      │
                    │  • Web Scraping      │
                    │  • LinkedIn (Apify)  │
                    │  • Company Data      │
                    │                      │
                    └──────────────────────┘
```

## Column Structure

The system manages the following lead information:

1. **Full Name** - Lead's full name
2. **Company Name** - Company name
3. **LinkedIn Link** - LinkedIn profile URL
4. **Company Size** - Company size category (Startup, Small, Medium, Large, Enterprise)
5. **Industry** - Company industry
6. **Company Revenue Estimated** - Estimated company revenue
7. **Job Role** - Lead's job title/position
8. **Company year EST** - Year company was established
9. **Phone** - Contact phone number
10. **Salesperson** - Assigned salesperson (filtered by "Dareen")
11. **Quality (Out of 5)** - Data quality score (1-5)
12. **Enriched** - Enrichment status (Yes/No/Partial/Failed)

## 🚀 Quick Start

### Method 1: One-Click Startup (Recommended)

**Windows:**
```bash
# Double-click start.bat or run in terminal:
start.bat
```

**Linux/Mac:**
```bash
# Make executable and run:
chmod +x start.sh
./start.sh
```

**Python (Any OS):**
```bash
python start.py
```

### Method 2: Development Mode

```bash
# For development with hot reload:
python start.py --dev

# Backend only:
python start.py --backend-only

# Setup only (install dependencies and build):
python start.py --setup
```

## 📋 Prerequisites

- **Python 3.8 or higher**
- **Node.js 16+ and npm** (for web interface)
- **Google Cloud Console account** (for Sheets API)
- **Apify account** (optional, for LinkedIn enrichment)
- **Access to your Odoo instance**

### 3. Configuration

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure Odoo settings in `.env`:**
   ```env
   ODOO_URL=https://your-odoo-instance.com
   ODOO_DB=your-database-name
   ODOO_USERNAME=your-username@example.com
   ODOO_PASSWORD=your-password
   ODOO_INSECURE_SSL=1
   ```

3. **Setup Google Sheets API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Sheets API
   - Create service account credentials
   - Download the JSON key file and save as `google_service_account.json`
   - Configure in `.env`:
   ```env
   GOOGLE_SERVICE_ACCOUNT_FILE=./google_service_account.json
   GSHEET_SPREADSHEET_TITLE=Lead Automation System
   GSHEET_SHARE_WITH=your-email@example.com
   ```

4. **Setup Apify (Optional - for LinkedIn enrichment):**
   - Create account at [Apify](https://apify.com/)
   - Get your API token from dashboard
   - Configure in `.env`:
   ```env
   APIFY_API_TOKEN=your-apify-token
   ```

5. **Configure processing settings:**
   ```env
   SALESPERSON_NAME=Dareen Fuqaha
   BATCH_SIZE=50
   MAX_CONCURRENT_REQUESTS=5
   ```

## 🎯 How to Use (Marketing Executive Workflow)

### Step 1: Launch the Application
1. **Run the startup script**: `start.bat` (Windows) or `./start.sh` (Linux/Mac)
2. **Open your browser** and go to: `http://localhost:8000`
3. **You'll see the beautiful dashboard** with three main action buttons

### Step 2: Extract Leads from Odoo
1. **Click "Extract Leads"** button on the dashboard
2. **Watch real-time progress** as the system connects to Odoo
3. **See the results**: Number of unenriched leads found

### Step 3: Enrich the Leads
1. **Click "Start Enrichment"** button
2. **Monitor live progress** with detailed status updates
3. **See enrichment results**: Company data, LinkedIn profiles, quality scores

### Step 4: Send Updated Info to Odoo
1. **Click "Run Full Pipeline"** for complete automation, or
2. **The system automatically updates** Odoo with enriched data and quality scores

### 🔍 Additional Features
- **View Leads**: Go to "Leads" page to see all leads in a beautiful table
- **Filter & Search**: Use the search and filter options to find specific leads
- **Configuration**: Visit "Settings" to manage system configuration
- **Real-time Updates**: All operations show live progress with WebSocket updates

## 💻 Web Interface

### Dashboard Features
- **📊 Real-time Statistics**: Live counts of leads, success rates, and performance metrics
- **🎯 One-Click Operations**: Three main buttons for the complete workflow
- **📈 Progress Tracking**: Live progress bars with detailed status messages
- **⚙️ System Status**: Configuration validation and connectivity status

### Leads Management
- **📋 Interactive Table**: View all leads with sorting and filtering
- **🔍 Advanced Search**: Search by name, email, company, or any field
- **⭐ Quality Ratings**: Visual star ratings for lead quality scores
- **✅ Status Tracking**: Clear indicators for enriched vs. unenriched leads
- **📤 Export Options**: Export filtered results to various formats

### Configuration Management
- **🔧 Visual Setup**: Easy-to-use interface for all system settings
- **✅ Validation**: Real-time configuration validation with helpful error messages
- **🔗 Integration Status**: Clear status indicators for all connected services
- **📖 Setup Guides**: Built-in instructions for complex integrations

## 🖥️ Command Line Interface (Optional)

The original CLI is still available for advanced users:

```bash
# Run full pipeline
python main.py

# Enrich specific leads
python main.py --leads 123 456 789

# Validate configuration
python main.py --validate

# Show system information
python main.py --info
```

## 📁 File Structure

```
Lead-Automation-System/
├── 🚀 start.py               # Smart startup script
├── 🚀 start.bat              # Windows startup script  
├── 🚀 start.sh               # Linux/Mac startup script
├── main.py                   # CLI orchestrator (legacy)
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies (enhanced)
├── .env.example             # Environment variables template
├── extract_odoo_leads.py    # Standalone Odoo extraction
├── README.md                # This documentation
│
├── 🌐 api/                   # FastAPI Backend
│   ├── __init__.py
│   └── main.py              # API server with WebSocket support
│
├── 🎨 frontend/              # React Web Interface
│   ├── package.json         # Frontend dependencies
│   ├── tailwind.config.js   # Tailwind CSS configuration
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── App.tsx          # Main React application
│       ├── index.tsx        # React entry point
│       ├── index.css        # Global styles with Tailwind
│       ├── components/      # Reusable UI components
│       │   ├── Layout.tsx   # Main layout with navigation
│       │   ├── ProgressBar.tsx
│       │   ├── StatsCard.tsx
│       │   └── ActionButton.tsx
│       ├── pages/           # Main application pages
│       │   ├── Dashboard.tsx    # Main dashboard
│       │   ├── LeadsPage.tsx    # Lead management
│       │   └── ConfigPage.tsx   # Configuration UI
│       ├── hooks/           # React hooks
│       │   └── useWebSocket.tsx # WebSocket integration
│       └── utils/           # Utility functions
│           └── api.ts       # API client
│
├── 🔧 modules/               # Core Python Modules
│   ├── __init__.py
│   ├── odoo_client.py       # Odoo integration
│   ├── sheets_client.py     # Google Sheets integration
│   ├── web_scraper.py       # Web scraping functionality
│   ├── linkedin_enricher.py # LinkedIn enrichment via Apify
│   ├── enrichment_pipeline.py # Main pipeline logic
│   └── logger.py            # Logging configuration
│
└── 📊 logs/                  # Log files (auto-created)
    ├── lead_automation.log  # Main log file
    ├── errors.log           # Error-only log
    └── daily_YYYYMMDD.log  # Daily logs
```

## Logging

The system provides comprehensive logging:

- **Console Output**: Real-time progress updates
- **Main Log**: All operations (`logs/lead_automation.log`)
- **Error Log**: Errors only (`logs/errors.log`)
- **Daily Logs**: Daily operation logs (`logs/daily_YYYYMMDD.log`)

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`

## Data Quality Scoring

The system calculates a quality score (1-5) based on:

- **Data Completeness**: How many fields are populated
- **Enrichment Success**: Whether data was successfully enriched
- **LinkedIn Presence**: Whether LinkedIn profile was found
- **Website Data**: Whether company website provided information

## Error Handling

The system includes robust error handling:

- **Connection Errors**: Retry mechanisms for API calls
- **Data Validation**: Validates data before processing
- **Graceful Degradation**: Continues processing even if some enrichments fail
- **Detailed Logging**: All errors are logged with context

## Troubleshooting

### Common Issues

1. **"Google Service Account file not found"**
   - Ensure the JSON file path is correct in `.env`
   - Check file permissions

2. **"Authentication to Odoo failed"**
   - Verify Odoo credentials in `.env`
   - Check if the Odoo instance is accessible
   - Try setting `ODOO_INSECURE_SSL=1` for staging environments

3. **"LinkedIn enrichment disabled"**
   - Add your Apify API token to `.env`
   - Verify Apify account has sufficient credits

4. **"No leads found"**
   - Check if there are leads assigned to the specified salesperson
   - Verify the salesperson name matches exactly in Odoo

### Performance Tuning

- Adjust `BATCH_SIZE` for optimal processing speed
- Modify `MAX_CONCURRENT_REQUESTS` based on API limits
- Use `--log-level ERROR` to reduce log verbosity

## Security Notes

- Never commit `.env` file or service account JSON to version control
- Use environment variables for all sensitive configuration
- Regularly rotate API tokens and credentials
- Review Google Sheets sharing permissions

## Support

For issues and questions:
1. Check the logs in the `logs/` directory
2. Run with `--validate` to check configuration
3. Use `--log-level DEBUG` for detailed troubleshooting
4. Review the error messages in console output

## License

This project is proprietary software for internal use.