# API Limits ERR-Q429

ERR-Q429 indicates the tenant request quota was exceeded. The standard limit is 120 requests per minute. Honor Retry-After before retrying safe idempotent GET requests. POST order creation requires an idempotency key.
