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

AO / Org (org_type = ao | region):
```
{
  "id": 123,
  "parent_id": 45 | null,         // region id for AOs; null for top-level region
  "org_type": "ao" | "region" | "area" | "sector" | "nation",
  "default_location_id": 789 | null,
  "name": "Shovel Flag AO",
  "description": "…" | null,
  "is_active": true,
  "logo_url": "https://…" | null,
  "website": "https://…" | null,
  "email": "…" | null,
  "twitter": "…" | null,
  "facebook": "…" | null,
  "instagram": "…" | null,
  "last_annual_review": "2025-01-31" | null,
  "meta": { "slack_channel_id": "C012345" } | {},
  "ao_count": 12,
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

Location:
```
{
  "id": 456,
  "org_id": 123,
  "name": "The Pit",
  "description": "…" | null,
  "is_active": true,
  "email": "…" | null,
  "latitude": 35.12345 | null,
  "longitude": -80.98765 | null,
  "address_street": "123 Main St" | null,
  "address_street2": "Suite 100" | null,
  "address_city": "Charlotte" | null,
  "address_state": "NC" | null,
  "address_zip": "28202" | null,
  "address_country": "USA" | null,
  "meta": { … } | {},
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

EventType:
```
{
  "id": 789,
  "name": "Bootcamp",
  "description": "…" | null,
  "acronym": "BC" | null,
  "event_category": "first_f" | "second_f" | "third_f",
  "specific_org_id": 123 | null,
  "is_active": true,
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

EventTag:
```
{
  "id": 1011,
  "name": "CSAUP",
  "description": "…" | null,
  "color": "#32CD32" | "green" | null,
  "specific_org_id": 123 | null,
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

Event (Series):
```
{
  "id": 111,
  "org_id": 123,
  "location_id": 456 | null,
  "is_active": true,
  "highlight": false,
  "start_date": "2025-02-01",
  "end_date": "2025-12-31" | null,
  "start_time": "0530" | null,
  "end_time": "0615" | null,
  "day_of_week": "monday" | null,
  "name": "Shovel Flag Bootcamp",
  "description": "…" | null,
  "email": "…" | null,
  "recurrence_pattern": "weekly" | "monthly" | null,
  "recurrence_interval": 1 | null,
  "index_within_interval": 1 | null,
  "meta": { … } | {},
  "event_types": [ {EventType...} ],
  "event_tags": [ {EventTag...} ],
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

EventInstance:
```
{
  "id": 222,
  "org_id": 123,
  "location_id": 456 | null,
  "series_id": 111 | null,
  "is_active": true,
  "highlight": false,
  "name": "Shovel Flag Bootcamp",
  "description": "…" | null,
  "start_date": "2025-02-10",
  "end_date": "2025-02-10" | null,
  "start_time": "0530" | null,
  "end_time": "0615" | null,
  "preblast_rich": { … } | null,
  "preblast": "…" | null,
  "preblast_ts": "2025-02-09T12:34:56Z" | null,
  "event_types": [ {EventType...} ],
  "event_tags": [ {EventTag...} ],
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

---

## Endpoint Summary

| Purpose | Method | Path |
|---------|--------|------|
| [1. Get region with selectable data](#1-get-region--dependencies) | GET | /regions/{region_id}?include=locations,event_types,event_tags |
| [2. List AOs for region](#2-list-aos-under-region) | GET | /regions/{region_id}/aos |
| [3. Create AO](#3-create-ao) | POST | /aos |
| [4. Get AO by id](#4-get-ao) | GET | /aos/{ao_id} |
| [5. Update AO (partial)](#5-update-ao-partial) | PATCH | /aos/{ao_id} |
| [6. Deactivate AO](#6-deactivate-soft-delete-ao) | DELETE | /aos/{ao_id} |
| [7. Batch deactivate events for AO](#7-batch-deactivate-events-explicit) | POST | /aos/{ao_id}/deactivate-events |
| [8. Batch deactivate future event instances](#8-batch-deactivate-future-event-instances) | POST | /aos/{ao_id}/deactivate-future-event-instances |
| [9. File upload (logo)](#9-file-upload-logo) | POST | /files |
| [10. Trigger map revalidation](#10-trigger-map-revalidation) | POST | /admin/map/revalidate |
| [11. List Locations (region)](#11-list-locations-region) | GET | /regions/{region_id}/locations?is_active=true |
| [12. Create Location](#12-create-location) | POST | /locations |
| [13. Get Location](#13-get-location) | GET | /locations/{location_id} |
| [14. Update Location](#14-update-location-partial) | PATCH | /locations/{location_id} |
| [15. Delete Location](#15-delete-deactivate-location) | DELETE | /locations/{location_id} |
| [16. List Event Types (region)](#16-list-event-types-region) | GET | /regions/{region_id}/event-types?is_active=true |
| [17. List Available External Event Types](#17-list-available-external-event-types-not-yet-imported) | GET | /regions/{region_id}/event-types/available |
| [18. Import External Event Type](#18-import-external-event-type) | POST | /regions/{region_id}/event-types/import |
| [19. Create Event Type](#19-create-event-type) | POST | /event-types |
| [20. Update Region Event Type](#20-update-region-event-type) | PATCH | /event-types/{event_type_id} |
| [21. Delete Region Event Type](#21-delete-region-event-type) | DELETE | /event-types/{event_type_id} |
| [22. List Event Tags (region)](#22-list-event-tags-region) | GET | /regions/{region_id}/event-tags |
| [23. List Available Global Event Tags](#23-list-available-global-event-tags) | GET | /regions/{region_id}/event-tags/available |
| [24. Import Global Event Tag into Region](#24-import-global-event-tag-into-region) | POST | /regions/{region_id}/event-tags/import |
| [25. Create Event Tag](#25-create-event-tag) | POST | /event-tags |
| [26. Update Region Event Tag](#26-update-region-event-tag) | PATCH | /event-tags/{event_tag_id} |
| [27. Delete Region Event Tag](#27-delete-region-event-tag) | DELETE | /event-tags/{event_tag_id} |
| [28. List Event Instances (region)](#28-list-event-instances-region) | GET | /regions/{region_id}/event-instances |
| [29. Create Event Instance](#29-create-event-instance) | POST | /event-instances |
| [30. Get Event Instance](#30-get-event-instance) | GET | /event-instances/{event_instance_id} |
| [31. Update Event Instance](#31-update-event-instance) | PATCH | /event-instances/{event_instance_id} |
| [32. Delete (Deactivate) Event Instance](#32-delete-deactivate-event-instance) | DELETE | /event-instances/{event_instance_id} |
| [33. List Series (Events) for Region](#33-list-series-events-region) | GET | /regions/{region_id}/events |
| [34. Create Series (Event)](#34-create-series-event) | POST | /events |
| [35. Get Series (Event)](#35-get-series-event) | GET | /events/{event_id} |
| [36. Update Series (Event)](#36-update-series-event) | PATCH | /events/{event_id} |
| [37. Delete Series (Event)](#37-delete-series-event) | DELETE | /events/{event_id} |
| [38. Refresh/Generate Instances for Series](#38-refreshgenerate-instances-for-series) | POST | /events/{event_id}/refresh-instances |
| [39. Map Update Webhook](#39-map-update-webhook) | POST | /admin/map/updates |

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

GET /regions/{region_id}/locations?is_active=true&scope=all|region|ao&limit=50&offset=0

Query Params:
- is_active (optional, default true) — filter by active status
- scope (optional, default all):
  - all: union of locations owned by the region AND by AOs under that region (matches current Slack UX)
  - region: only locations whose org_id = region_id
  - ao: only locations whose org_id is an AO with parent_id = region_id
- limit, offset (optional) — pagination

Response 200:
```
{
  "results": [ {Location...} ],
  "pagination": { "limit": 50, "offset": 0, "total": 123 }
}
```

Errors:
- 404 region_not_found

Notes:
- This endpoint backs the “Edit/Delete a Location” list used in the Slack UI.
- For map accuracy, clients SHOULD call /admin/map/revalidate after create/update/delete operations.

---
---

## 12. Create Location

POST /locations

Request JSON:
```
{
  "region_id": 123,                   // required
  "name": "Central Park - Main Entrance",
  "description": "Meet at the flagpole near the entrance",
  "latitude": 34.0522,
  "longitude": -118.2437,
  "address_street": "123 Main St.",
  "address_street2": "Suite 200",
  "address_city": "Los Angeles",
  "address_state": "CA",
  "address_zip": "90210",
  "address_country": "USA"
}
```

Behavior:
- Validate region exists (org_type=region).
- Create Location owned by the region (org_id=region_id), is_active=true.
- On success, clients SHOULD trigger map revalidation (/admin/map/revalidate).

Response 201:
```
{Location...}
```

Errors:
- 400 missing_field (e.g., region_id, name, latitude, longitude)
- 400 invalid_coordinates
- 404 region_not_found

---

## 13. Get Location

GET /locations/{location_id}

Response 200:
```
{Location...}
```

Errors:
- 404 location_not_found

---

## 14. Update Location (Partial)

PATCH /locations/{location_id}

Request JSON (any subset):
```
{
  "name": "New Name",
  "description": "Updated notes",
  "latitude": 35.0000,
  "longitude": -117.0000,
  "address_street": "456 Elm St.",
  "address_city": "Burbank",
  "address_state": "CA",
  "address_zip": "91502",
  "address_country": "USA",
  "is_active": true
}
```

Rules:
- Only provided fields change.
- Ownership (org_id) is immutable via this endpoint.
- On success, clients SHOULD trigger map revalidation (/admin/map/revalidate).

Response 200:
```
{Location...}
```

Errors:
- 400 invalid_coordinates
- 404 location_not_found

---

## 15. Delete (Deactivate) Location

DELETE /locations/{location_id}

Behavior:
- Soft delete by setting is_active=false.
- If the location is referenced as an AO’s default_location_id or by active events, server MAY reject with conflict or accept and leave references (client responsibility). Initial behavior: accept and leave references.
- On success, clients SHOULD trigger map revalidation (/admin/map/revalidate).

Response 200:
```
{ "location_id": 789, "status": "deactivated" }
```

Errors:
- 404 location_not_found
- 409 conflict (optional, if enforcing reference checks)

---

## 16. List Event Types (Region)

Lists event types visible to a region. Visibility rules mirror current Slack workflow:
1. Global event types (specific_org_id = null)
2. Region-owned event types (specific_org_id = region_id)

Optional filtering of scope (similar to Event Tags) and active flag.

GET /regions/{region_id}/event-types?is_active=true&scope=all|region|global

Query Params:
- is_active (optional, default true) — filter by active status
- scope (optional, default all):
  - all: union of global + region
  - region: only region-owned
  - global: only global

Response 200:
```
{
  "results": [
    {
      "id": 7,
      "name": "Bootcamp",
      "event_category": "first_f",
      "acronym": "BC",
      "specific_org_id": null,
      "is_active": true,
      "created": "2025-01-02T12:34:56Z",
      "updated": "2025-03-04T08:10:00Z"
    }
  ]
}
```

Errors:
- 404 region_not_found

---

## 17. List Available External Event Types (Not Yet Imported)
---

## 18. Import External Event Type

POST /regions/{region_id}/event-types/import

Request JSON:
```
{
  "source_event_type_id": 999,   // id in another region
  "new_name": "optional rename"  // optional; default = source name
}
```

Behavior:
- Copy an external, active event type owned by another region (specific_org_id != region_id) into this region.
- Excludes global types (specific_org_id = null) since they’re already visible.

Response 201:
```
{EventType...}
```

Errors:
- 404 region_not_found
- 404 source_not_found
- 409 name_conflict

---

## 19. Create Event Type

POST /event-types

Request JSON:
```
{
  "region_id": 123,     // owning region (specific_org_id)
  "name": "Bootcamp",
  "is_active": true
}
```

Response 201:
```
{EventType...}
```

Errors:
- 400 missing_field
- 404 region_not_found
- 409 name_conflict

---

## 20. Update Region Event Type

PATCH /event-types/{event_type_id}

Request JSON (any subset):
```
{
  "name": "New Name",
  "is_active": true
}
```

Response 200:
```
{EventType...}
```

Errors:
- 404 event_type_not_found
- 409 name_conflict

---

## 21. Delete Region Event Type

DELETE /event-types/{event_type_id}

Behavior:
- Soft delete by setting is_active=false.

Response 200:
```
{ "event_type_id": 789, "status": "deactivated" }
```

Errors:
- 404 event_type_not_found

---

## 22. List Event Tags (region)

GET /regions/{region_id}/event-tags

Query Params:
- is_active (optional, default true)
- scope (optional, default all):
  - all: union of global + region
  - global: only global
  - region: only region-owned

Response 200:
```
{ "results": [ {EventTag...} ] }
```

Errors:
- 404 region_not_found

---

## 23. List Available Global Event Tags

GET /regions/{region_id}/event-tags/available

Response 200:
```
{ "results": [ {EventTag...} ] }
```

Errors:
- 404 region_not_found

---

## 24. Import Global Event Tag into Region

POST /regions/{region_id}/event-tags/import

Request JSON:
```
{ "global_event_tag_id": 321 }
```

Response 201:
```
{EventTag...}
```

Errors:
- 404 region_not_found
- 404 event_tag_not_found
- 409 name_conflict

---

## 25. Create Event Tag

POST /event-tags

Request JSON:
```
{ "region_id": 123, "name": "CSAUP", "is_active": true }
```

Response 201:
```
{EventTag...}
```

Errors:
- 404 region_not_found
- 409 name_conflict

---

## 26. Update Region Event Tag

PATCH /event-tags/{event_tag_id}

Request JSON (subset):
```
{ "name": "New Name", "is_active": false }
```

Response 200:
```
{EventTag...}
```

Errors:
- 404 event_tag_not_found
- 409 name_conflict

---

## 27. Delete Region Event Tag

DELETE /event-tags/{event_tag_id}

Behavior: Soft delete (is_active=false).

Response 200:
```
{ "event_tag_id": 123, "status": "deactivated" }
```

Errors:
- 404 event_tag_not_found

---

## 28. List Event Instances (Region)

GET /regions/{region_id}/event-instances?is_active=true&ao_id={ao_id}&date=YYYY-MM-DD&from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50&offset=0

Purpose: backs the “Manage Event Instances” list and the AO/Date filters in the Slack UI used by `event_instance.py`.

Query Params:
- is_active (optional, default true)
- ao_id (optional) — filter by AO (Org.id where org_type=ao and parent_id=region_id)
- date (optional) — filter by specific date (start_date in local/region context)
- from, to (optional) — inclusive date range; if provided, ignores `date`
- limit, offset (pagination)

Response 200:
```
{
  "results": [ {EventInstance...} ],
  "pagination": { "limit": 50, "offset": 0, "total": 123 }
}
```

Errors:
- 404 region_not_found

---

## 29. Create Event Instance

POST /event-instances

Request JSON:
```
{
  "ao_id": 123,                 // Org.id with org_type=ao
  "location_id": 456,
  "event_type_id": 789,
  "event_tag_id": 1011,         // optional; at most one supported by Slack UI today
  "start_date": "2025-01-20",  // local date (region time)
  "start_time": "05:30",
  "end_time": "06:15",         // optional; default = start_time + 1h
  "name": "Optional name",     // if omitted: defaults to "{AO name} {EventType name}"
  "description": "Optional text", // optional
  "highlight": false,           // optional; default false
  "preblast_rich": { ... },     // optional Slack rich text JSON
  "preblast": "<formatted text>" // optional plain text
}
```

Behavior:
- Validates AO belongs to region; Location and EventType are active and visible to that region.
- Creates EventInstance and attaches tag (EventTag_x_EventInstance) if provided.

Response 201:
```
{EventInstance...}
```

Errors:
- 400 missing_field / invalid_time
- 404 ao_not_found | location_not_found | event_type_not_found | event_tag_not_found

---

## 30. Get Event Instance

GET /event-instances/{event_instance_id}

Response 200:
```
{EventInstance...}
```

Errors:
- 404 event_instance_not_found

---

## 31. Update Event Instance

PATCH /event-instances/{event_instance_id}

Request JSON (any subset):
```
{
  "location_id": 456,
  "event_type_id": 789,
  "event_tag_id": 1011,  // set or clear (null)
  "start_date": "2025-01-21",
  "start_time": "05:30",
  "end_time": "06:30",
  "name": "New Name",
  "description": "Updated text",
  "highlight": true,
  "preblast_rich": { ... },
  "preblast": "<formatted text>",
  "preblast_ts": "2025-01-19T20:15:00Z" // optional; set when posted
}
```

Behavior:
- Only provided fields change. Handles tag attach/detach via EventTag_x_EventInstance.

Response 200:
```
{EventInstance...}
```

Errors:
- 404 event_instance_not_found
- 400 invalid_time

---

## 32. Delete (Deactivate) Event Instance

DELETE /event-instances/{event_instance_id}

Behavior: Soft delete (is_active=false).

Response 200:
```
{ "event_instance_id": 321, "status": "deactivated" }
```

Errors:
- 404 event_instance_not_found

---

## 33. List Series (Events) for Region

GET /regions/{region_id}/events?is_active=true&ao_id={ao_id}&limit=50&offset=0

Purpose: backs the “Manage Series” list used by `series.py`.

Query Params:
- is_active (optional, default true)
- ao_id (optional) — filter to a specific AO in the region
- limit, offset (pagination)

Response 200:
```
{
  "results": [ {Event...} ],
  "pagination": { "limit": 50, "offset": 0, "total": 42 }
}
```

Errors:
- 404 region_not_found

---

## 34. Create Series (Event)

POST /events

Request JSON:
```
{
  "ao_id": 123,                     // owning AO
  "default_location_id": 456,
  "default_event_type_id": 789,
  "default_event_tag_id": 1011,     // optional, single tag
  "start_date": "2025-02-01",
  "end_date": "2025-12-31",        // optional (open-ended)
  "start_time": "05:30",
  "end_time": "06:15",             // optional; default = +1h
  "days_of_week": ["monday", "wednesday"],  // Day_Of_Week enum names
  "interval": 1,                    // e.g., every 1 or 2 weeks/months
  "frequency": "weekly",           // Event_Cadence: weekly | monthly
  "index": 1,                       // which week of month (if monthly)
  "name": "Series Name",           // optional; default AO + event type
  "description": "Optional text",  // optional
  "highlight": false                // optional
}
```

Behavior:
- Persists `Event` (series) with cadence and defaults (Location, EventType, optional EventTag).
- Does not automatically generate instances unless `generate_instances=true` is requested (optional query param).

Response 201:
```
{Event...}
```

Errors:
- 400 missing_field / invalid_schedule
- 404 ao_not_found | location_not_found | event_type_not_found | event_tag_not_found

---

## 35. Get Series (Event)

GET /events/{event_id}

Response 200:
```
{Event...}
```

Errors:
- 404 event_not_found

---

## 36. Update Series (Event)

PATCH /events/{event_id}

Request JSON (any subset):
```
{
  "default_location_id": 456,
  "default_event_type_id": 789,
  "default_event_tag_id": null,
  "start_date": "2025-02-10",
  "end_date": "2025-12-31",
  "start_time": "05:45",
  "end_time": "06:30",
  "days_of_week": ["tuesday"],
  "interval": 2,
  "frequency": "monthly",
  "index": 2,
  "name": "Updated Name",
  "description": "Updated description",
  "highlight": true
}
```

Query Params:
- propagate_future=true|false (default true) — if true, apply updated defaults (location, time, description, tags/types, highlight) to future EventInstances without regenerating schedule.

Behavior:
- Only provided fields change. When cadence-related fields change, future instance generation may need to be refreshed separately. If `propagate_future=true`, server will update future instances’ metadata to match the new defaults.

Response 200:
```
{Event...}
```

Errors:
- 404 event_not_found
- 400 invalid_schedule

---

## 37. Delete Series (Event)

DELETE /events/{event_id}

Behavior: Soft delete (is_active=false). Optionally cascade deactivate future instances.

Query Params:
- deactivate_future_instances=true|false (default true)

Response 200:
```
{ "event_id": 111, "future_instances_deactivated": 24 }
```

Errors:
- 404 event_not_found

---

## 38. Refresh/Generate Instances for Series

POST /events/{event_id}/refresh-instances

Request JSON:
```
{
  "from_date": "2025-02-01",      // default: today (UTC or region TZ)
  "clear_existing_from_date": true // default true; prevents duplicates
}
```

Behavior:
- Generates EventInstance rows from the series’ cadence starting at `from_date`.
- If `clear_existing_from_date` is true, deactivates or removes future instances from `from_date` before regenerating.

Response 200:
```
{ "event_id": 111, "event_instances_created": 52 }
```

Errors:
- 404 event_not_found
- 400 invalid_date_range

---

## 39. Map Update Webhook

POST /admin/map/updates

Purpose: inbound webhook from the map service to notify of map-created/updated/deleted actions that should sync series instances.

Request JSON:
```
{
  "version": "1.0",
  "timestamp": "2025-05-07T19:45:12Z",
  "action": "map.updated", // or map.created | map.deleted
  "data": {
    "eventId": 1123,    // optional
    "locationId": 987,  // optional
    "orgId": 456        // optional
  }
}
```

Behavior:
- On map.created/map.updated with eventId, refresh/generate that series’ future instances (clear-first as needed).
- map.deleted with eventId may deactivate the series or future instances (implementation-defined).

Response 200:
```
{ "status": "ok" }
```

Errors:
- 400 invalid_payload

Returns active event types that are owned by other regions (specific_org_id != region_id AND not null) that the region has not already copied. These are analogous to the "commonly used" list in the Slack modal (see `event_type.py`). Global types (specific_org_id = null) are excluded because they are already visible without import.

GET /regions/{region_id}/event-types/available

Response 200:
```
{
  "results": [ {EventType...} ]
}
```

Errors:
- 404 region_not_found

---

## 20. Import (Copy) External Event Type Into Region

Creates a region-owned copy of another region's event type. Copies name, event_category, acronym. Sets specific_org_id=region_id. Enforces uniqueness of name within region (case-insensitive). (Acronym uniqueness recommended but optional — enforce if desired.)

POST /regions/{region_id}/event-types/import

Request JSON:
```
{
  "source_event_type_id": 42
}
```

Behavior:
- Validate region exists (org_type=region)
- Validate source event type exists and has specific_org_id != region_id (and not null)
- Check for name conflict within region
- Insert new EventType row (specific_org_id=region_id, copying fields)

Response 201:
```
{EventType...}
```

Errors:
- 400 missing_field
- 404 region_not_found
- 404 event_type_not_found
- 409 duplicate_name

---

## 21. Create Event Type

POST /event-types

Request JSON:
```
{
  "region_id": 123,                 // required
  "name": "Ruck Heavy",
  "event_category": "first_f",
  "acronym": "RH"                  // optional; default = first two letters of name uppercased
}
```

Behavior:
- Verify region exists (org_type=region)
- Require name and event_category
- Enforce uniqueness of name (and optionally acronym) within region (case-insensitive)
- Validate event_category in allowed enum values (first_f, second_f, third_f)
- Insert with specific_org_id=region_id, is_active=true

Response 201:
```
{EventType...}
```

Errors:
- 400 missing_field (e.g., region_id, name, event_category)
- 400 invalid_event_category
- 404 region_not_found
- 409 duplicate_name

---

## 22. Update Region Event Type

PATCH /event-types/{event_type_id}

Request JSON (any subset):
```
{
  "name": "New Name",
  "event_category": "second_f",
  "acronym": "NN",
  "is_active": true   // optional; allow reactivation or soft deactivation toggle
}
```

Rules:
- Only region-owned event types (specific_org_id != null) can be updated; global types must be copied first
- Cannot change specific_org_id directly
- Maintain uniqueness constraints

Response 200:
```
{EventType...}
```

Errors:
- 400 invalid_event_category
- 403 forbidden (attempt to modify a global event type)
- 404 event_type_not_found
- 409 duplicate_name

---

## 23. Delete (Deactivate) Region Event Type

DELETE /event-types/{event_type_id}

Behavior:
- Soft delete by setting is_active=false (mirrors current Slack flow which toggles is_active)
- Only region-owned types deletable; global types immutable
- (Alternative extension: support hard delete if no events reference it — optional, not required now)

Response 200:
```
{ "event_type_id": 55, "status": "deactivated" }
```

Errors:
- 403 forbidden (attempt to delete a global event type)
- 404 event_type_not_found

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

## 16. Create Event Tag

POST /event-tags

Request JSON:
```
{
  "region_id": 123,           // required
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
- 400 missing_field (e.g., region_id, name)
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
