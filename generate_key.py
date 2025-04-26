import secrets

# Generate a secure random key (32 bytes is a common length)
key = secrets.token_hex(32)

print(f"Generated Secret Key: {key}")
print("Set this key as the SECRET_KEY environment variable for your Flask app.") 