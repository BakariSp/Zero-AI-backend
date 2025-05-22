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

# Zero-AI Backend User Cards Fix

## Problem Description

The application was encountering 404 errors when trying to access user cards with routes like:
```
"PUT /api/users/me/cards/2787 HTTP/1.1" 404 Not Found
```

The issue was that when cards were generated (either through learning paths or AI chat), they were being created in the database but **not being associated with users in the `user_cards` table**. This association is crucial for tracking user progress and personalizing the learning experience.

## Solution

We've implemented both a one-time fix script and permanent changes to the codebase:

1. **Fix Script (`fix_user_cards.py`)** - A utility script that finds all cards that are part of a user's learning paths but not in their user_cards table, and creates the missing associations.

2. **Code Changes** - We've updated the following files to ensure cards are automatically associated with users when created:
   - `app/services/background_tasks.py`
   - `app/services/learning_path_planner.py`

## Running the Fix Script

To fix existing data in your database:

```bash
# Fix for all users
python fix_user_cards.py

# Fix for a specific user
python fix_user_cards.py --user-id 123
```

The script will:
1. Identify missing user-card associations
2. Show you how many cards need to be fixed
3. Ask for confirmation before making changes
4. Add the missing entries to the user_cards table
5. Report the results

## Code Changes Made

We updated the following functions to automatically associate cards with users:

1. Added `user_id` parameter to card generation functions
2. Added code to call `save_card_for_user()` after creating each card
3. Ensured the functions properly handle any errors that might occur during the association

## Testing the Fix

After applying these changes, you should:

1. Run the fix script to repair existing data
2. Create a new learning path and verify cards are properly linked to the user
3. Try accessing user cards via the API to confirm they return 200 OK instead of 404

## Monitoring

Look for the following log messages to confirm cards are being properly associated with users:
```
Associated card {card_id} with user {user_id} in user_cards table
```

If you see error messages like:
```
Failed to associate card {card_id} with user {user_id}: {error}
```
then there might be an issue with the database or permissions.

