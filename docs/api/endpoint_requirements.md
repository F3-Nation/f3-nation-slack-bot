# API Endpoint Documentation

## Authentication & Authorization

All endpoints require an authenticated user/session.  
Recommended scopes:
- read:org
- write:org
- read:location
- read:event-type
- write:event
- admin:maintenance (for map revalidation)

---

## Data Model (API Projection)

AO (Org where org_type = ao):
```
{
  "id": int,
  "parent_id": int,            // region org id
  "name": string,
  "description": string|null,
  "is_active": boolean,
  "default_location_id": int|null,
  "meta": { "slack_channel_id": "CXXXX" } | {},
  "logo_url": string|null,
  "website": string|null,
  "email": string|null,
  "twitter": string|null,
  "facebook": string|null,
  "instagram": string|null,
  "created": datetime,
  "updated": datetime
}
```

Location (subset needed):
```
{
  "id": int,
  "name": string,
  "is_active": boolean,
  "latitude": float|null,
  "longitude": float|null
}
```

EventType (subset needed):
```
{
  "id": int,
  "name": string,
  "event_category": "first_f" | "second_f" | "third_f",
  "is_active": boolean
}
```

---

## Endpoint Summary

| Purpose | Method | Path |
|---------|--------|------|
| Get region with selectable data | GET | /regions/{region_id}?include=locations,event_types |
| List AOs for region | GET | /regions/{region_id}/aos |
| Create AO | POST | /aos |
| Get AO by id | GET | /aos/{ao_id} |
| Update AO (partial) | PATCH | /aos/{ao_id} |
| Deactivate AO | DELETE | /aos/{ao_id} |
| Batch deactivate events for AO | POST | /aos/{ao_id}/deactivate-events |
| Batch deactivate future event instances | POST | /aos/{ao_id}/deactivate-future-event-instances |
| File upload (logo) | POST | /files |
| Trigger map revalidation | POST | /admin/map/revalidate |
| List Locations (region) | GET | /regions/{region_id}/locations?is_active=true |
| List Event Types (region) | GET | /regions/{region_id}/event-types?is_active=true |

---

## 1. Get Region + Dependencies

GET /regions/{region_id}?include=locations,event_types

Query Params:
- include: CSV of relationships. Supported: locations,event_types

Response 200:
```
{
  "id": 123,
  "name": "Region Name",
  "locations": [ {Location...} ],
  "event_types": [ {EventType...} ]
}
```

---

## 2. List AOs Under Region

GET /regions/{region_id}/aos?is_active=true

Query Params:
- is_active (optional, default true)
- limit, offset (pagination)

Response 200:
```
{
  "results": [ {AO...} ],
  "pagination": { "limit": 50, "offset": 0, "total": 17 }
}
```

---

## 3. Create AO

POST /aos

Request JSON:
```
{
  "region_id": 123,
  "name": "The Coliseum",
  "description": "Bootcamp style",
  "slack_channel_id": "C012ABC",
  "default_location_id": 45,
  "logo_file_id": "uploaded-ref" | null
}
```

Behavior:
- Validate region_id exists and org_type = region
- Create Org with org_type=ao, parent_id=region_id
- meta.slack_channel_id = slack_channel_id
- If logo_file_id present, resolve to URL (from file service)
- Returns AO representation

Response 201:
```
{AO...}
```

Error Codes:
- 400 missing_field
- 404 region_not_found
- 409 duplicate_name (if enforcing uniqueness within region)

---

## 4. Get AO

GET /aos/{ao_id}

Query Params:
- include=location (optional)
- (future) include=events,count

Response 200:
```
{AO...}
```

404 if not found or inactive (unless ?include_inactive=true).

---

## 5. Update AO (Partial)

PATCH /aos/{ao_id}

Request JSON (any subset):
```
{
  "name": "New Name",
  "description": "Updated",
  "default_location_id": 55,
  "slack_channel_id": "C999NEW",
  "logo_file_id": "new-upload-id"   // optional; if omitted, keep existing
}
```

Rules:
- Only provided fields change
- slack_channel_id updates meta.slack_channel_id
- logo_file_id resolves to new logo_url
- Cannot directly change parent_id or org_type

Response 200:
```
{AO...}
```

Errors:
- 400 invalid_location
- 404 ao_not_found
- 409 name_conflict

---

## 6. Deactivate (Soft Delete) AO

DELETE /aos/{ao_id}

Behavior:
- Set is_active=false
- Optionally cascade per flags (query params):
  - ?deactivate_events=true (default true)
  - ?deactivate_future_instances=true (default true)
- Enqueue map revalidation (async) or return instruction to client to call map endpoint

Response 200:
```
{
  "ao_id": 456,
  "status": "deactivated",
  "events_deactivated": 23,
  "future_instances_deactivated": 87
}
```

---

## 7. Batch Deactivate Events (Explicit)

POST /aos/{ao_id}/deactivate-events

Request JSON:
```
{
  "deactivate_after": "2025-01-01"   // optional cutoff; if omitted, all
}
```

Response 200:
```
{ "ao_id": 456, "events_updated": 23 }
```

---

## 8. Batch Deactivate Future Event Instances

POST /aos/{ao_id}/deactivate-future-event-instances

Request JSON:
```
{
  "from_date": "2025-02-20"   // default = today (UTC)
}
```

Response 200:
```
{ "ao_id": 456, "event_instances_updated": 54 }
```

---

## 9. File Upload (Logo)

POST /files

Multipart/Form-Data:
- file: binary
- purpose=ao_logo

Response 201:
```
{
  "file_id": "abc123",
  "url": "https://cdn.example.com/logos/abc123.png",
  "mime_type": "image/png",
  "width": 512,
  "height": 512
}
```

Then client supplies file_id to AO create/update.

---

## 10. Trigger Map Revalidation

POST /admin/map/revalidate

Request JSON:
```
{
  "scope": "region" | "ao" | "all",
  "region_id": 123,
  "ao_id": 456
}
```

Response 202:
```
{ "status": "queued", "job_id": "uuid" }
```

---

## 11. List Locations (Region)

GET /regions/{region_id}/locations?is_active=true

Response 200:
```
{
  "results": [ {Location...} ]
}
```

---

## 12. List Event Types (Region)

GET /regions/{region_id}/event-types?is_active=true

Response 200:
```
{
  "results": [ {EventType...} ]
}
```

---

## Error Schema (General)

```
{
  "error": {
    "code": "ao_not_found",
    "message": "AO not found",
    "detail": {}
  }
}
```

Common codes: ao_not_found, region_not_found, invalid_location, unauthorized, forbidden, validation_error, duplicate_name.

---

## Versioning

Prefix with /v1 (recommended):
- /v1/aos
- /v1/regions/{region_id}/aos
- /v1/admin/map/revalidate

---

## OpenAPI Tags

- AOs
- Regions
- Locations
- Event Types
- Events (cascade ops)
- Files
- Admin

---

## Minimal Required Endpoints Set

If constrained, the absolute minimum to replicate existing UI:
1. GET /regions/{region_id}?include=locations,event_types
2. GET /regions/{region_id}/aos
3. POST /aos
4. PATCH /aos/{ao_id}
5. DELETE /aos/{ao_id}
6. POST /files
7. POST /admin/map/revalidate

(The cascade deactivations could be server-side inside DELETE logic initially.)

---
