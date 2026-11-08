// Fixed public messages only: never relay provider bodies or document text.
export const serviceErrors: Record<string, string> = {
  invalid_citation:
    "The answer failed source verification. No unverified answer was shown. Try a narrower question.",
  llm_invalid_output:
    "The model returned an invalid answer format. Please retry.",
  llm_incomplete_output:
    "The model reached its response limit. Try a more focused question.",
  llm_request_rejected:
    "The answer provider rejected the request. Check the server's model configuration.",
  llm_not_authorized:
    "The answer provider rejected its credentials. Check the server configuration.",
  llm_rate_limited:
    "The answer provider is rate limited or has exhausted its quota. Check provider billing and retry later.",
  llm_timeout: "The answer provider timed out. Please retry.",
  llm_refused: "The answer provider declined this request.",
  llm_request_failed: "The answer provider request failed. Please retry.",
  database_unavailable:
    "The knowledge database is unavailable. Check the backend database connection.",
};
