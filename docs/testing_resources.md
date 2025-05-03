# Testing URL Validation and Resource Enhancement

This document explains how to use the testing scripts for validating URLs and enhancing card resources using Google Search API.

## Prerequisites

Before using these scripts, ensure you have:

1. Set up Google Custom Search API (see [Google API Setup](google_api_setup.md))
2. Added the required API keys to your `.env` file:
   ```
   GOOGLE_API_KEY=your_google_api_key
   GOOGLE_SEARCH_CX=your_custom_search_engine_id
   ```
3. Installed all dependencies from `requirements.txt`

## Testing Scripts

There are two main scripts for testing URL validation and resource enhancement:

1. `scripts/test_url_validator.py` - For testing individual URLs and search queries
2. `scripts/audit_card_resources.py` - For auditing all cards in the database and fixing invalid URLs

### Test URL Validator Script

This script allows you to test different components of the URL validation system.

#### Available Commands

1. **Validate a URL**:
   ```bash
   python scripts/test_url_validator.py validate "https://example.com"
   ```

2. **Test Google Search**:
   ```bash
   python scripts/test_url_validator.py search "Python programming tutorial" --num 5
   ```

3. **Test Resource Enhancement**:
   ```bash
   python scripts/test_url_validator.py enhance "Machine Learning" --context "beginners guide"
   ```

   You can also provide custom resources to test:
   ```bash
   python scripts/test_url_validator.py enhance "Python" --resources '[{"url": "https://example.com/invalid", "title": "Invalid Resource"}, {"url": "https://www.python.org", "title": "Valid Resource"}]'
   ```

4. **Test Card Generation**:
   ```bash
   python scripts/test_url_validator.py generate "Machine Learning" --context "overview for beginners"
   ```

5. **Run a Batch Test**:
   ```bash
   python scripts/test_url_validator.py batch
   ```
   This will run multiple test cases and report the results.

### Audit Card Resources Script

This script audits all cards in the database, identifies invalid URLs, and can fix them automatically.

#### Available Options

- `--limit N`: Limit the audit to N cards (useful for testing)
- `--fix`: Automatically fix invalid resources using Google Search
- `--summary`: Show only summary statistics, not detailed results
- `--output FILE`: Save the audit results to a JSON file

#### Example Usage

1. **Audit all cards without fixing**:
   ```bash
   python scripts/audit_card_resources.py
   ```

2. **Audit and automatically fix invalid resources**:
   ```bash
   python scripts/audit_card_resources.py --fix
   ```

3. **Test on a limited number of cards**:
   ```bash
   python scripts/audit_card_resources.py --limit 50
   ```

4. **Save results to a file**:
   ```bash
   python scripts/audit_card_resources.py --output audit_results.json
   ```

## Interpreting Results

### Test URL Validator

The output of the URL validator tests will be in JSON format, showing:

- For URL validation: whether the URL is valid and accessible
- For Google Search: the search results with titles and URLs
- For resource enhancement: the original resources and enhanced resources
- For card generation: the complete card data with validated resources

### Audit Card Resources

The audit will show a summary of the results:

```
===== Card Resources Audit Summary =====
Total cards checked: 100
Valid cards: 75 (75.0%)
Invalid cards: 25
Cards fixed: 20
Failed fixes: 5
```

If you save the results to a file, you'll get a detailed report showing:
- Valid card IDs
- Invalid cards with details of invalid resources
- Fixed cards with before/after resources
- Failed fix IDs

## Troubleshooting

1. **API Key Issues**: If you see "Google Search API key or CX not configured" errors, check your `.env` file.

2. **Rate Limiting**: Google Search API has limits (100 queries/day for free). If you hit the limit, you'll see errors.

3. **Connection Issues**: If URL validation fails for all URLs, check your internet connection.

4. **Database Access**: If you can't access the database, verify your database connection settings.

## Best Practices

- Start with small tests using the `test_url_validator.py` script
- When running the audit, use `--limit` to test on a small set first
- Review the audit results before running with `--fix`
- Monitor the `card_resources_audit.log` file for detailed error information 