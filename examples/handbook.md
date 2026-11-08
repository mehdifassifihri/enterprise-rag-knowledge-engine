# Example Company Knowledge Handbook

## Purpose

This fictional handbook is a safe sample for testing the Enterprise Knowledge Engine ingestion pipeline. It contains no customer data, credentials, or personal information. Uploaded source bytes are hashed with SHA-256 so repeated uploads can be detected within the authenticated tenant.

## Access policy

Every document belongs to a tenant. The server derives the tenant from a configured API key binding. Callers cannot select another tenant through form fields or request headers. Documents uploaded by one tenant must not appear in another tenant's document list.

## Onboarding

New team members should read the engineering handbook and review the service ownership register. Each service has a named owner, an escalation procedure, and an operational checklist. Keep procedures short, specific, and easy to verify. Update documents when the actual process changes.

## Incident handling

Record the observed behavior, affected systems, timeline, and recovery steps. Include reproducible checks where possible. Do not paste secrets into incident reports or application logs. After recovery, identify follow-up actions with clear owners and verification criteria.

## Document lifecycle

The ingestion pipeline extracts readable text, normalizes whitespace, splits text into overlapping chunks, and generates vector embeddings. Chunks keep their order and source offsets. Text-based PDF chunks also retain the original page number. Image-only PDFs require OCR, which is outside this project's current scope.

## Verification

A document is ready only after its chunks and embeddings are committed successfully. A failed embedding call must leave a failed document with no partial chunks. A retry of the same source bytes should reuse the document identifier. Deleting a document removes its chunks and vectors through a database cascade.
