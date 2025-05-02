#!/usr/bin/env python
"""
This script patches the OAuth flow to automatically accept terms of service
for users who sign in through OAuth providers (Google, Microsoft).

To apply this patch, run:
    python oauth_terms_patch.py

The patch adds code to the OAuth callback handlers to call the auto_accept_terms_for_oauth_user
function after a user has successfully authenticated.
"""

import os
import sys
import re
from pathlib import Path

# Add the parent directory to the Python path (if not already there)
parent_dir = os.path.dirname(os.path.abspath(__file__))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

OAUTH_FILE_PATH = "app/auth/oauth.py"
TERMS_VERSION = "v1.0"  # Default terms version

def patch_microsoft_handler():
    """Add terms acceptance code to Microsoft OAuth handler"""
    file_path = os.path.join(parent_dir, OAUTH_FILE_PATH)
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Find the appropriate location to add the code
    # We want to add it right after the user creation/retrieval, before creating the access token
    pattern = r'(# Create JWT access token for the user\s+access_token = create_access_token\(data=\{"sub": user\.email\}\))'
    
    # The code to insert
    terms_code = (
        '            # Auto-accept terms of service for OAuth users\n'
        '            from app.users.crud import auto_accept_terms_for_oauth_user\n'
        '            client_ip = request.client.host if hasattr(request, "client") and hasattr(request.client, "host") else "0.0.0.0"\n'
        f'            auto_accept_terms_for_oauth_user(db, user.id, terms_version="{TERMS_VERSION}", ip_address=client_ip)\n'
        '            log.info(f"Auto-accepted terms for user {user.email}")\n\n            '
    )
    
    # Replace with the modified code
    modified_content = re.sub(pattern, terms_code + r'\1', content)
    
    # Write back to the file
    with open(file_path, 'w') as file:
        file.write(modified_content)
    
    print(f"Added terms acceptance to Microsoft OAuth handler in {file_path}")

def patch_google_handler():
    """Add terms acceptance code to Google OAuth handler"""
    file_path = os.path.join(parent_dir, OAUTH_FILE_PATH)
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Find the callback function for Google OAuth
    start_pattern = r'@router\.get\("/google/callback", name="auth_via_google"\)'
    callback_match = re.search(start_pattern, content)
    
    if not callback_match:
        print("Could not find Google OAuth callback handler.")
        return
    
    # Find the location where the access token is created
    pattern = r'(# Create access token\s+access_token = create_access_token\(data=\{"sub": user\.email\}\))'
    
    # The code to insert
    terms_code = (
        '    # Auto-accept terms of service for OAuth users\n'
        '    from app.users.crud import auto_accept_terms_for_oauth_user\n'
        '    client_ip = request.client.host if hasattr(request, "client") and hasattr(request.client, "host") else "0.0.0.0"\n'
        '    db = SessionLocal()\n'
        '    try:\n'
        f'        auto_accept_terms_for_oauth_user(db, user.id, terms_version="{TERMS_VERSION}", ip_address=client_ip)\n'
        '        print(f"Auto-accepted terms for user {user.email}")\n'
        '    finally:\n'
        '        db.close()\n\n    '
    )
    
    # Replace with the modified code
    modified_content = re.sub(pattern, terms_code + r'\1', content)
    
    # Write back to the file
    with open(file_path, 'w') as file:
        file.write(modified_content)
    
    print(f"Added terms acceptance to Google OAuth handler in {file_path}")

def patch_oauth_user_function():
    """Add terms acceptance to the get_oauth_user function, which handles both providers"""
    file_path = os.path.join(parent_dir, OAUTH_FILE_PATH)
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Find the location after creating/finding the user in get_oauth_user function
    pattern = r'(log\.info\(f"Found existing user: \{user\.username\}"\))(\s+)finally:'
    
    # The code to insert
    terms_code = (
        r'\1\n\n            # Auto-accept terms of service for OAuth users\n'
        '            from app.users.crud import auto_accept_terms_for_oauth_user\n'
        '            client_ip = request.client.host if hasattr(request, "client") and hasattr(request.client, "host") else "0.0.0.0"\n'
        f'            auto_accept_terms_for_oauth_user(db, user.id, terms_version="{TERMS_VERSION}", ip_address=client_ip)\n'
        '            log.info(f"Auto-accepted terms for user {user.email}")\n'
    )
    
    # Replace with the modified code
    modified_content = re.sub(pattern, terms_code + r'\2finally:', content)
    
    # Write back to the file
    with open(file_path, 'w') as file:
        file.write(modified_content)
    
    print(f"Added terms acceptance to get_oauth_user function in {file_path}")

def add_terms_acceptance_to_readme():
    """Add information about terms acceptance to the README"""
    readme_path = os.path.join(parent_dir, "README.md")
    
    if not os.path.exists(readme_path):
        print("README.md not found. Skipping README update.")
        return
    
    with open(readme_path, 'r') as file:
        content = file.read()
    
    # Check if terms section already exists
    if "## Terms of Service Acceptance" in content:
        print("Terms section already exists in README. Skipping update.")
        return
    
    # Add terms section to the README
    terms_section = """
## Terms of Service Acceptance

The system automatically records when users accept the Terms of Service:

- For standard login/registration, users must explicitly accept the terms through the UI.
- For OAuth users (Google, Microsoft), terms are automatically accepted upon login.
- Admin scripts are available to manage terms acceptance:
  - `accept_terms_for_users.py`: Accept terms for all users or specific users
  - `oauth_terms_patch.py`: Patch the OAuth flow to auto-accept terms

See `docs/terms_api.md` for the complete API documentation.
"""
    
    # Append to the README
    with open(readme_path, 'a') as file:
        file.write(terms_section)
    
    print(f"Added terms acceptance information to {readme_path}")

def update_terms_api_doc():
    """Update the terms API documentation with information about OAuth auto-acceptance"""
    doc_path = os.path.join(parent_dir, "docs/terms_api.md")
    
    if not os.path.exists(doc_path):
        print("docs/terms_api.md not found. Skipping documentation update.")
        return
    
    with open(doc_path, 'r') as file:
        content = file.read()
    
    # Check if OAuth section already exists
    if "### OAuth Users" in content:
        print("OAuth section already exists in documentation. Skipping update.")
        return
    
    # Find the best practices section to add our new section right before it
    pattern = r'(## Best Practices)'
    
    # The section to insert
    oauth_section = """
### OAuth Users

For users who sign in through OAuth providers (Google, Microsoft), terms are automatically accepted on their behalf. This ensures all users are covered by the terms of service, even if they skip the standard registration flow.

The system:
1. Records acceptance with the user's IP address when available
2. Uses the current terms version (currently set to "v1.0")
3. Only records this once per terms version per user

OAuth auto-acceptance can be modified by editing the `oauth_terms_patch.py` script and re-running it.

\1"""
    
    # Replace with the modified content
    modified_content = re.sub(pattern, oauth_section, content)
    
    # Write back to the file
    with open(doc_path, 'w') as file:
        file.write(modified_content)
    
    print(f"Updated terms API documentation in {doc_path}")

if __name__ == "__main__":
    print("Patching OAuth flow to auto-accept terms of service...")
    
    # Apply all patches
    patch_oauth_user_function()  # This covers both Google and Microsoft in one place
    update_terms_api_doc()
    add_terms_acceptance_to_readme()
    
    print("\nPatches applied successfully!")
    print(f"Terms version used: {TERMS_VERSION}")
    print("\nTo change the terms version used for auto-acceptance:")
    print("1. Edit the TERMS_VERSION variable in this script")
    print("2. Run this script again")
    print("\nDone!") 