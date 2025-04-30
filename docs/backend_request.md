# CORS OPTIONS Request Handling Guide

## Overview

This document outlines how to properly handle preflight OPTIONS requests that browsers automatically send before certain cross-origin requests, including PATCH, PUT, DELETE methods, or requests with custom headers.

## OPTIONS Request Format

When the frontend makes a cross-origin request that requires preflight (like a PATCH request to update a calendar task), the browser automatically sends an OPTIONS request first. This is what the request looks like:

```
OPTIONS /api/calendar/tasks/9 HTTP/1.1
Host: localhost:8000
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
Origin: http://localhost:3000
Access-Control-Request-Method: PATCH
Access-Control-Request-Headers: content-type, authorization
Accept: */*
Connection: keep-alive
Referer: http://localhost:3000/
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: same-site
```

### Key Headers to Note

- `Access-Control-Request-Method`: Indicates which HTTP method will be used in the actual request (PATCH in this case)
- `Access-Control-Request-Headers`: Lists the custom headers the actual request will include (content-type, authorization)
- `Origin`: The origin from which the request is being made (http://localhost:3000)

## Required Response Headers for OPTIONS

The backend must respond to OPTIONS requests with the following headers:

```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, Accept
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
Content-Length: 0
```

### Header Explanations

- `Access-Control-Allow-Origin`: Specifies which origins are allowed to access the resource. Use the exact origin from the request or `*` for all origins (cannot use `*` with credentials).
- `Access-Control-Allow-Methods`: Lists all HTTP methods that are allowed for the resource.
- `Access-Control-Allow-Headers`: Lists all headers that can be used when making the actual request. Must include all headers specified in `Access-Control-Request-Headers`.
- `Access-Control-Allow-Credentials`: Set to `true` if requests can include credentials (cookies, HTTP authentication).
- `Access-Control-Max-Age`: How long (in seconds) the preflight response can be cached.

## FastAPI Implementation Example

For a FastAPI backend, you can implement CORS handling as follows:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # List all allowed origins or use ["*"]
    allow_credentials=True,                   # Set to True if using cookies/auth
    allow_methods=["*"],                      # Allow all methods or list specific ones
    allow_headers=["*"],                      # Allow all headers or list specific ones
    max_age=86400,                            # Cache preflight response for 24 hours
)

# Your API routes here
```

## Express.js Implementation Example

For an Express.js backend:

```javascript
const express = require('express');
const cors = require('cors');
const app = express();

const corsOptions = {
  origin: 'http://localhost:3000',
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization', 'Accept'],
  credentials: true,
  maxAge: 86400
};

app.use(cors(corsOptions));

// Your API routes here
```

## Manual Implementation in Any Backend

If you need to handle OPTIONS requests manually:

```
// Example pseudo-code
IF request.method === 'OPTIONS' THEN
    response.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Max-Age'] = '86400'
    response.status = 200
    response.end()
ELSE
    // Process the actual request
END
```

## Troubleshooting

If you're still encountering CORS errors:

1. **Verify Headers**: Ensure that the headers in the OPTIONS response exactly match what the browser expects.
2. **Check Origin**: Ensure the `Access-Control-Allow-Origin` header matches the Origin header from the request.
3. **Credentials**: If using `credentials: true`, you cannot use `*` for `Access-Control-Allow-Origin`.
4. **Headers Mismatch**: Ensure that all headers in `Access-Control-Request-Headers` are included in `Access-Control-Allow-Headers`.
5. **Methods Mismatch**: Ensure the method in `Access-Control-Request-Method` is included in `Access-Control-Allow-Methods`.
6. **Network Inspection**: Use browser developer tools (Network tab) to inspect the OPTIONS request and its response.

## Example of a Failed OPTIONS Response

Here's what a failed OPTIONS response might look like:

```
HTTP/1.1 400 Bad Request
Date: Wed, 30 Apr 2025 07:07:22 GMT
Server: uvicorn
Content-Length: 42
Content-Type: application/json

{"detail":"Missing required Authorization header"}
```

The issue here is that the server is trying to process the OPTIONS request as a regular request requiring authentication, rather than treating it as a preflight request that should be handled separately.

## Example of a Successful OPTIONS Response

A successful response is typically empty with a 200 status code and the appropriate CORS headers:

```
HTTP/1.1 200 OK
Date: Wed, 30 Apr 2025 07:07:22 GMT
Server: uvicorn
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, Accept
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 86400
Content-Length: 0
```

After receiving this response, the browser will proceed with the actual PATCH request.
