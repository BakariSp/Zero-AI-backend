# Setting Up Google Custom Search API

This document explains how to set up the Google Custom Search API for use with the card resource validation and enhancement feature.

## Prerequisites

1. A Google Account
2. A Google Cloud Platform project

## Steps to Set Up Google Custom Search API

### 1. Create or Select a Google Cloud Platform Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Click on the project dropdown and select an existing project or click "NEW PROJECT" to create a new one
3. Follow the prompts to name your project and select billing information if necessary

### 2. Enable the Custom Search API

1. In your Google Cloud Console, navigate to "APIs & Services" > "Library"
2. Search for "Custom Search API" 
3. Click on "Custom Search API" in the results
4. Click "ENABLE" to enable the API for your project

### 3. Create API Credentials

1. In your Google Cloud Console, navigate to "APIs & Services" > "Credentials"
2. Click "+ CREATE CREDENTIALS" at the top of the page and select "API key"
3. Your new API key will be displayed. Copy this key as you'll need it later
4. (Optional but recommended) Click "Restrict key" to limit which APIs can use this key, selecting only "Custom Search API"

### 4. Set Up a Custom Search Engine

1. Go to the [Programmable Search Engine Control Panel](https://programmablesearchengine.google.com/controlpanel/all)
2. Click "Add" to create a new search engine
3. Enter the sites you want to search, or select "Search the entire web" for general searches
4. Give your search engine a name
5. Click "CREATE"

### 5. Get Your Custom Search Engine ID

1. After creating your search engine, click on it in your search engine list
2. Click on "Setup" in the left navigation
3. Find your "Search engine ID" under "Basics" - this is your `cx` parameter (also known as the Custom Search Engine ID)

### 6. Update Your Environment Variables

Add the following environment variables to your `.env` file:

```
GOOGLE_API_KEY=your_google_api_key
GOOGLE_SEARCH_CX=your_custom_search_engine_id
```

## Usage

With the API key and Custom Search Engine ID set up in your environment variables, the system will automatically validate URLs in card resources and replace invalid ones with resources found via Google Search when generating cards.

## Troubleshooting

- **API Key Not Working**: Ensure the API key has been properly restricted to the Custom Search API
- **Quota Exceeded**: Check your quotas in the Google Cloud Console
- **No Results**: Ensure your Custom Search Engine is configured correctly

## Rate Limits

Please note that the Google Custom Search API has the following limitations:
- 100 search queries per day for free
- For higher volume, you'll need to enable billing and pay per query

For more information on pricing, visit the [Google Custom Search API pricing page](https://developers.google.com/custom-search/v1/overview#pricing). 