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

EventTag (subset needed):
```
{
  "id": int,
  "name": string,
  "color": string,                 // hex or palette value (see EVENT_TAG_COLORS)
  "specific_org_id": int|null,     // null => global (available to all); int => region-owned copy
  "created": datetime,
  "updated": datetime
}
```

---

## Endpoint Summary

| Purpose | Method | Path |
|---------|--------|------|
| Get region with selectable data | GET | /regions/{region_id}?include=locations,event_types,event_tags |
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
| List Event Tags (region) | GET | /regions/{region_id}/event-tags |
| List Available Global Event Tags | GET | /regions/{region_id}/event-tags/available |
| Import Global Event Tag into Region | POST | /regions/{region_id}/event-tags/import |
| Create Region Event Tag | POST | /regions/{region_id}/event-tags |
| Update Region Event Tag | PATCH | /event-tags/{event_tag_id} |
| Delete Region Event Tag | DELETE | /event-tags/{event_tag_id} |

---

## 1. Get Region + Dependencies

GET /regions/{region_id}?include=locations,event_types,event_tags

Query Params:
- include: CSV of relationships. Supported: locations,event_types,event_tags

Response 200:
```
{
  "id": 123,
  "name": "Region Name",
  "locations": [ {Location...} ],
  "event_types": [ {EventType...} ],
  "event_tags": [ {EventTag...} ]
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

## 13. List Event Tags (Region)

Lists event tags visible to the region including:
1. Region-owned tags (specific_org_id = region_id)
2. Global tags (specific_org_id = null)

By default both sets are returned. Use the optional `scope` query param to filter.

GET /regions/{region_id}/event-tags?scope=all|region|global

Query Params:
- scope (optional, default = all):
  - all: union of region + global
  - region: only region-owned tags
  - global: only global tags

Response 200 (flat list; global tags have specific_org_id = null):
```
{
  "results": [ {EventTag...} ]
}
```

Errors:
- 404 region_not_found

---

## 14. List Available Global Event Tags (Not Yet Imported)

Returns global event tags (specific_org_id = null) that the region has not already imported (i.e., no region-owned tag with same name/color combination). Used to populate the select list in the Slack modal.

GET /regions/{region_id}/event-tags/available

Response 200:
```
{
  "results": [ {EventTag...} ]
}
```

Errors:
- 404 region_not_found

---

## 15. Import (Add) Global Event Tag to Region

Creates a region-owned copy of a global tag (duplicating name + color, setting specific_org_id = region_id). Mirrors current behavior in `EventTagService.add_global_tag_to_org`.

POST /regions/{region_id}/event-tags/import

Request JSON:
```
{
  "global_tag_id": 42
}
```

Behavior:
- Validate region exists (org_type=region)
- Validate the referenced tag exists and is global (specific_org_id = null)
- Check for name conflict within region (case-insensitive)
- Insert new EventTag row

Response 201:
```
{EventTag...}
```

Errors:
- 400 missing_field
- 404 region_not_found
- 404 event_tag_not_found
- 409 duplicate_name

---

## 16. Create Region-Specific Event Tag

POST /regions/{region_id}/event-tags

Request JSON:
```
{
  "name": "CSA Dropoff",
  "color": "green" | "#32CD32"
}
```

Behavior:
- Verify region exists (org_type=region)
- Enforce uniqueness of name within region
- Validate color against allowed palette (optional — align with EVENT_TAG_COLORS)
- Create tag (specific_org_id=region_id)

Response 201:
```
{EventTag...}
```

Errors:
- 400 missing_field
- 400 invalid_color
- 404 region_not_found
- 409 duplicate_name

---

## 17. Update Region Event Tag

PATCH /event-tags/{event_tag_id}

Request JSON (any subset):
```
{
  "name": "New Tag Name",
  "color": "purple"
}
```

Rules:
- Only region-owned tags (specific_org_id != null) can be updated; global tags must be imported first
- Maintain uniqueness of name within the same region

Response 200:
```
{EventTag...}
```

Errors:
- 400 invalid_color
- 403 forbidden (attempt to modify a global tag directly)
- 404 event_tag_not_found
- 409 duplicate_name

---

## 18. Delete Region Event Tag

DELETE /event-tags/{event_tag_id}

Behavior:
- Only region-owned tags deletable
- Implementation choice: hard delete (current Slack flow) vs soft delete (add is_active column). If soft delete chosen, modify Data Model accordingly.

Response 200:
```
{ "event_tag_id": 77, "status": "deleted" }
```

Errors:
- 403 forbidden (attempt to delete a global tag)
- 404 event_tag_not_found

---

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

Common codes: ao_not_found, region_not_found, invalid_location, unauthorized, forbidden, validation_error, duplicate_name, event_tag_not_found, invalid_color.

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
