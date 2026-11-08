# Expected behavior, not an execution transcript

| Scenario | Script assertion |
|---|---|
| Upload each synthetic document | HTTP success, ready status, positive persisted chunk count |
| Repeat upload | HTTP 409 |
| List/get | Same uploaded IDs and chunk counts |
| Keyword / vector / hybrid | Nonempty tenant-A results, no tenant-B document IDs |
| Supported retail returns question | answered, one authorized citation |
| Returns plus portal submission | answered, two authorized citations |
| Executive bonus outside corpus | insufficient_evidence, no citations |
| Device-service document with malicious text | scripted FACT answer; canary excluded |
| Cross-tenant get/delete | 404; original remains visible to owner |
| Tenant-B list/search/ask | no tenant-A IDs or citation metadata |
| Official MCP SDK subprocess | tools discoverable, search and cited QA succeed |

The identical-vector and scripted-answer fixtures are intentional. They cannot establish semantic quality, entailment or security of a real model. Full MCP tenant/readonly/error coverage lives in the integration suite. See FINAL_VERIFICATION for executed versus pending checks.
