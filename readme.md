## Backend Architecture

Zero-AI backend is built on Azure cloud services, providing the following core functionalities:

- **Knowledge Graph Construction**: Utilizes Azure AI services to process user-input keyword cards and automatically build knowledge connections
- **Personalized Learning Paths**: Generates customized learning plans based on the user's current knowledge level
- **Authentication**: Integrates Microsoft/Google account login systems
- **Data Storage**: Efficiently manages user learning progress and knowledge structures
- **Intelligent Recommendations**: Suggests relevant content based on learning behavior analysis
- **Resource Validation**: Validates and enhances card resources using URL validation and Google Search API

### Tech Stack

- **Azure AI Services**: Provides AI models and natural language processing capabilities
- **Azure Web Services**: Hosts APIs and application logic
- **Azure MySQL**: Stores user data and knowledge graphs
- **Google Custom Search API**: Enhances card resources with valid and relevant URLs

### Quick Start

1. Clone the repository
2. Configure Azure service connections
3. Set up app registration and authentication
4. Set up Google Custom Search API (see [Google API Setup](docs/google_api_setup.md))
5. Deploy to Azure Web Services

### Environment Setup

Create a `.env` file with the following variables:
```
# Database configuration
DATABASE_URL=mysql+pymysql://user:password@localhost/dbname

# JWT Secret Key
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name

# Google Search API configuration
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_CX=your_custom_search_engine_id
```

### To run the project locally
uvicorn main:app --reload --host 127.0.0.1 --port 8000

### New Features

#### URL Validation and Resource Enhancement
The system now validates URLs in card resources and automatically replaces invalid URLs with high-quality resources fetched from Google Search API. This ensures that all educational cards provide working, relevant external resources for the users.

#### Testing Scripts
Two testing scripts are provided to help validate and test the URL validation and resource enhancement features:

1. **URL Validator Test Script**: Test individual URLs, Google Search, and resource enhancement
   ```bash
   python scripts/test_url_validator.py [command] [options]
   ```

2. **Card Resources Audit Script**: Audit existing cards in the database and fix invalid URLs
   ```bash
   python scripts/audit_card_resources.py [options]
   ```

For detailed instructions on using these scripts, see [Testing Resources](docs/testing_resources.md).

