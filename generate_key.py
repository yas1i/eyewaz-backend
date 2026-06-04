import secrets

# Generate a strong random secret key
jwt_secret_key = secrets.token_urlsafe(32)

print("JWT_SECRET_KEY:", jwt_secret_key)
