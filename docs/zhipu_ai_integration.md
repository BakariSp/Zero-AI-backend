# Zhipu AI GLM-4 Integration

This document explains how to configure and use the Zhipu AI GLM-4 model instead of Azure OpenAI in your backend.

## Overview

The backend now supports two AI service providers:

1. **Azure OpenAI** (default) - Microsoft's managed OpenAI service
2. **Zhipu AI GLM-4** - Chinese large language model from Zhipu AI

You can switch between these providers by changing the configuration in your `.env` file.

## Configuration

### 1. Get Zhipu AI API Key

To use GLM-4, you'll need to:

1. Create an account at [Zhipu AI](https://www.bigmodel.cn/)
2. Navigate to the API keys section
3. Create a new API key
4. Copy the API key (it should be in the format `ID.SECRET`)

### 2. Update .env File

Add the following settings to your `.env` file:

```
# Zhipu AI GLM-4 Configuration
USE_ZHIPU_AI=true
ZHIPU_AI_API_KEY=your_zhipu_api_key_here
ZHIPU_AI_MODEL=glm-4
ZHIPU_AI_CARD_MODEL=glm-4
```

- `USE_ZHIPU_AI`: Set to `true` to use Zhipu AI, `false` to use Azure OpenAI
- `ZHIPU_AI_API_KEY`: Your Zhipu AI API key
- `ZHIPU_AI_MODEL`: The model to use for general tasks (default: `glm-4`)
- `ZHIPU_AI_CARD_MODEL`: The model to use for card generation (default: `glm-4`)

### 3. Install Required Packages

Make sure you have the necessary packages installed:

```bash
pip install -r requirements.txt
```

## Testing the Integration

A test script is provided to verify that the Zhipu AI integration is working correctly:

```bash
python test_zhipu_ai.py
```

This script will:
1. Check if Zhipu AI is enabled in your `.env` file
2. Verify that a valid API key is provided
3. Make a test API call to GLM-4
4. Display the response

## Usage

Once configured, the application will automatically use GLM-4 for all AI operations. No code changes are needed in your application logic.

You can test the AI service using the `/test-ai` endpoint:

```
GET /test-ai
```

This endpoint will display information about which AI service is being used and return a sample response.

## Troubleshooting

### API Key Format

The Zhipu AI API key should be in the format `ID.SECRET`. If you're having authentication issues, verify that your API key has the correct format.

### Rate Limits

Zhipu AI may have different rate limits than Azure OpenAI. If you encounter rate limit errors, you may need to adjust your application's request patterns.

### Environment Variables

Run the environment check script to verify your configuration:

```bash
python check_env.py
```

### Network Issues

Ensure your server can reach the Zhipu AI API endpoints. The API is hosted at `https://open.bigmodel.cn/api/paas/v4`.

## Reverting to Azure OpenAI

To revert to using Azure OpenAI, simply set `USE_ZHIPU_AI=false` in your `.env` file or remove the line entirely. 