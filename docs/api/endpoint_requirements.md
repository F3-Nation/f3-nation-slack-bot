# API Endpoint Documentation

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
  "backblast_rich": { … } | null,
  "backblast": "…" | null,
  "backblast_ts": "2025-02-10T12:34:56Z" | null,
  "pax_count": 17 | null,
  "fng_count": 2 | null,
  "meta": { … } | {},                    // free-form, used for custom fields
  "event_types": [ {EventType...} ],
  "event_tags": [ {EventTag...} ],
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

User:
```
{
  "id": 9876,
  "f3_name": "Short Circuit",
  "home_region_id": 123 | null,
  "emergency_contact": "Jane Doe" | null,
  "emergency_phone": "+1 555-123-4567" | null,
  "emergency_notes": "Allergy: peanuts" | null,
  "avatar_url": "https://…" | null,
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

SlackUser:
```
{
  "id": 555,
  "user_id": 9876,
  "slack_id": "U012345",
  "slack_team_id": "T012345",
  "created": "2025-01-01T12:00:00Z",
  "updated": "2025-01-02T12:00:00Z"
}
```

SlackSpace Settings (projection used by config, welcome, custom fields, canvas):
```
{
  "team_id": "T0123456",                 // Slack workspace id
  "org_id": 123,                          // Region Org.id connected to this Slack workspace
  "workspace_name": "F3 Metro",          // optional
  // General
  "editing_locked": 0 | 1,
  "default_backblast_destination": "ao" | "region" | "specified_channel",
  "backblast_destination_channel": "C0123" | null,
  "default_preblast_destination": "ao" | "region" | "specified_channel",
  "preblast_destination_channel": "C0456" | null,
  "backblast_moleskin_template": "...",
  "preblast_moleskin_template": "...",
  "preblast_reminder_days": 0 | 1 | 2 | 3,
  "backblast_reminder_days": 0 | 1 | 2 | 3,
  "migration_date": "2025-06-01" | null,     // used by middleware to route legacy vs API
  // Email
  "email_enabled": 0 | 1,
  "email_option_show": 0 | 1,
  "email_user": "example_sender@gmail.com" | null,
  "email_to": "example_destination@gmail.com" | null,
  "email_server": "smtp.gmail.com" | null,
  "email_server_port": 587 | null,
  "email_password": "***masked***" | null,   // server returns masked; accepts plain text on update
  "postie_format": 0 | 1,
  // Welcome bot
  "welcome_dm_enable": 0 | 1,
  "welcome_dm_template": "...",              // Slack rich text JSON or string
  "welcome_channel_enable": 0 | 1,
  "welcome_channel": "C0789" | null,
  // Calendar + Canvas
  "send_q_lineups": true | false,
  "special_events_enabled": true | false,
  "special_events_post_days": 7,
  "calendar_image_current": "2025-08-01.png" | null,
  "canvas_channel": "C0CANVAS" | null,
  // Integrations
  "strava_enabled": 0 | 1,
  // Custom fields (for forms)
  "custom_fields": {
    "Event Type": { "name": "Event Type", "type": "Dropdown", "options": ["Bootcamp"], "enabled": true },
    "…": { }
  }
}
```

---

## Endpoint Summary

### Regions
| Purpose | Method | Path |
|---------|--------|------|
| [1. Get region with selectable data](#1-get-region--dependencies) | GET | /regions/{region_id}?include=locations,event_types,event_tags |
| [2. List AOs for region](#2-list-aos-under-region) | GET | /regions/{region_id}/aos |
| [11. List Locations (region)](#11-list-locations-region) | GET | /regions/{region_id}/locations?is_active=true |
| [16. List Event Types (region)](#16-list-event-types-region) | GET | /regions/{region_id}/event-types?is_active=true |
| [17. List Available External Event Types](#17-list-available-external-event-types-not-yet-imported) | GET | /regions/{region_id}/event-types/available |
| [18. Import External Event Type](#18-import-external-event-type) | POST | /regions/{region_id}/event-types/import |
| [22. List Event Tags (region)](#22-list-event-tags-region) | GET | /regions/{region_id}/event-tags |
| [23. List Available Global Event Tags](#23-list-available-global-event-tags) | GET | /regions/{region_id}/event-tags/available |
| [24. Import Global Event Tag into Region](#24-import-global-event-tag-into-region) | POST | /regions/{region_id}/event-tags/import |
| [28. List Event Instances (region)](#28-list-event-instances-region) | GET | /regions/{region_id}/event-instances |
| [33. List Series (Events) for Region](#33-list-series-events-region) | GET | /regions/{region_id}/events |
| [40. Calendar Home Schedule (Aggregated)](#40-calendar-home-schedule-aggregated) | GET | /regions/{region_id}/calendar/home |
| [45. List Region Admins](#45-list-region-admins) | GET | /regions/{region_id}/admins |
| [46. Add Region Admin](#46-add-region-admin) | POST | /regions/{region_id}/admins |
| [47. Remove Region Admin](#47-remove-region-admin) | DELETE | /regions/{region_id}/admins/{user_id} |
| [50. Update Region Profile](#50-update-region-profile) | PATCH | /regions/{region_id} |
| [51. Get Region Settings](#51-get-region-settings) | GET | /regions/{region_id}/settings |
| [52. Update Region Settings](#52-update-region-settings) | PATCH | /regions/{region_id}/settings |
| [62. Set Region Admins (Replace)](#62-set-region-admins-replace) | PUT | /regions/{region_id}/admins |
| [63. Trigger Canvas Rebuild](#63-trigger-canvas-rebuild) | POST | /regions/{region_id}/canvas/rebuild |
| [69. Search Regions (Typeahead)](#69-search-regions-typeahead) | GET | /regions/search |
| [71. List My Preblast Candidates](#71-list-my-preblast-candidates) | GET | /regions/{region_id}/preblast/candidates |

### AOs
| Purpose | Method | Path |
|---------|--------|------|
| [3. Create AO](#3-create-ao) | POST | /aos |
| [4. Get AO by id](#4-get-ao) | GET | /aos/{ao_id} |
| [5. Update AO (partial)](#5-update-ao-partial) | PATCH | /aos/{ao_id} |
| [6. Deactivate AO](#6-deactivate-soft-delete-ao) | DELETE | /aos/{ao_id} |
| [7. Batch deactivate events for AO](#7-batch-deactivate-events-explicit) | POST | /aos/{ao_id}/deactivate-events |
| [8. Batch deactivate future event instances](#8-batch-deactivate-future-event-instances) | POST | /aos/{ao_id}/deactivate-future-event-instances |

### Locations
| Purpose | Method | Path |
|---------|--------|------|
| [12. Create Location](#12-create-location) | POST | /locations |
| [13. Get Location](#13-get-location) | GET | /locations/{location_id} |
| [14. Update Location](#14-update-location-partial) | PATCH | /locations/{location_id} |
| [15. Delete Location](#15-delete-deactivate-location) | DELETE | /locations/{location_id} |

### Event Types
| Purpose | Method | Path |
|---------|--------|------|
| [19. Create Event Type](#19-create-event-type) | POST | /event-types |
| [20. Update Region Event Type](#20-update-region-event-type) | PATCH | /event-types/{event_type_id} |
| [21. Delete Region Event Type](#21-delete-region-event-type) | DELETE | /event-types/{event_type_id} |

### Event Tags
| Purpose | Method | Path |
|---------|--------|------|
| [25. Create Event Tag](#25-create-event-tag) | POST | /event-tags |
| [26. Update Region Event Tag](#26-update-region-event-tag) | PATCH | /event-tags/{event_tag_id} |
| [27. Delete Region Event Tag](#27-delete-region-event-tag) | DELETE | /event-tags/{event_tag_id} |

### Series (Events)
| Purpose | Method | Path |
|---------|--------|------|
| [34. Create Series (Event)](#34-create-series-event) | POST | /events |
| [35. Get Series (Event)](#35-get-series-event) | GET | /events/{event_id} |
| [36. Update Series (Event)](#36-update-series-event) | PATCH | /events/{event_id} |
| [37. Delete Series (Event)](#37-delete-series-event) | DELETE | /events/{event_id} |
| [38. Refresh/Generate Instances for Series](#38-refreshgenerate-instances-for-series) | POST | /events/{event_id}/refresh-instances |

### Event Instances
| Purpose | Method | Path |
|---------|--------|------|
| [29. Create Event Instance](#29-create-event-instance) | POST | /event-instances |
| [30. Get Event Instance](#30-get-event-instance) | GET | /event-instances/{event_instance_id} |
| [31. Update Event Instance](#31-update-event-instance) | PATCH | /event-instances/{event_instance_id} |
| [32. Delete (Deactivate) Event Instance](#32-delete-deactivate-event-instance) | DELETE | /event-instances/{event_instance_id} |
| [72. Update Preblast Draft](#72-update-preblast-draft) | PATCH | /event-instances/{event_instance_id}/preblast |
| [73. Mark Preblast Posted](#73-mark-preblast-posted) | POST | /event-instances/{event_instance_id}/preblast/posted |
| [74. Submit Backblast](#74-submit-backblast) | POST | /event-instances/{event_instance_id}/backblast |

### Attendance
| Purpose | Method | Path |
|---------|--------|------|
| [41. List Attendance (Event Instance)](#41-list-attendance-event-instance) | GET | /event-instances/{event_instance_id}/attendance |
| [42. Upsert Attendance (Event Instance)](#42-upsert-attendance-event-instance) | POST | /event-instances/{event_instance_id}/attendance |
| [43. Remove Attendance (Event Instance)](#43-remove-attendance-event-instance) | DELETE | /event-instances/{event_instance_id}/attendance |
| [44. Assign Q / Co-Q (Convenience)](#44-assign-q--co-q-convenience) | PUT | /event-instances/{event_instance_id}/q |

### Positions
| Purpose | Method | Path |
|---------|--------|------|
| [48. List Positions and Assigned Users](#48-list-positions-and-assigned-users) | GET | /orgs/{org_id}/positions |
| [57. Create Position](#57-create-position) | POST | /orgs/{org_id}/positions |
| [58. Update Position](#58-update-position) | PATCH | /positions/{position_id} |
| [59. Delete Position](#59-delete-position) | DELETE | /positions/{position_id} |
| [60. Assign Position to User](#60-assign-position-to-user) | POST | /orgs/{org_id}/positions/{position_id}/assign |
| [61. Unassign Position from User](#61-unassign-position-from-user) | DELETE | /orgs/{org_id}/positions/{position_id}/assign/{user_id} |

### Users
| Purpose | Method | Path |
|---------|--------|------|
| [66. Resolve User From Slack](#66-resolve-user-from-slack) | POST | /users/resolve-from-slack |
| [67. Get User](#67-get-user) | GET | /users/{user_id} |
| [68. Update User](#68-update-user) | PATCH | /users/{user_id} |
| [49. Get User Permissions (By Org)](#49-get-user-permissions-by-org) | GET | /users/{user_id}/permissions |
| [75. Search Users (Typeahead)](#75-search-users-typeahead) | GET | /users/search |

### Slack / SlackSpace
| Purpose | Method | Path |
|---------|--------|------|
| [64. Get SlackSpace by Team](#64-get-slackspace-by-team) | GET | /slack-spaces/{team_id} |
| [65. Update SlackSpace Settings by Team](#65-update-slackspace-settings-by-team) | PATCH | /slack-spaces/{team_id}/settings |
| [76. Create SlackSpace](#76-create-slackspace) | POST | /slack-spaces |
| [77. Connect SlackSpace to Org](#77-connect-slackspace-to-org) | POST | /slack-spaces/{team_id}/connect-org |
| [78. Sync Slack Users](#78-sync-slack-users) | POST | /slack-spaces/{team_id}/users/sync |
| [79. List Slack Users (Team)](#79-list-slack-users-team) | GET | /slack-spaces/{team_id}/slack-users |
| [70. Get Slack User Mapping](#70-get-slack-user-mapping) | GET | /slack-users/by-slack |
| [80. Migrate Slackblast Settings](#80-migrate-slackblast-settings) | POST | /admin/migrate/slackblast-settings |

### Files
| Purpose | Method | Path |
|---------|--------|------|
| [9. File upload (logo)](#9-file-upload-logo) | POST | /files |

### Admin
| Purpose | Method | Path |
|---------|--------|------|
| [10. Trigger map revalidation](#10-trigger-map-revalidation) | POST | /admin/map/revalidate |
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

## 16. List Event Types (Region)

GET /regions/{region_id}/event-types?is_active=true&include_global=true

Notes/Changes:
- include_global (optional, default true): if true, returns both event types owned by the region AND globally-available types (EventType.specific_org_id IS NULL). Mirrors current Slack UI behavior that queries region-specific or None.
- is_active (optional, default true).

Response 200:
```
{
  "results": [ {EventType...} ],
  "pagination": { "limit": 50, "offset": 0, "total": 37 }
}
```

---

## 28. List Event Instances (Region)

GET /regions/{region_id}/event-instances?ao_ids=1,2&event_type_ids=3,4&start_date=2025-01-01&end_date=2025-01-31&is_active=true&limit=100&offset=0

Notes/Changes:
- Supports filtering by one or more AO ids (orgs where org_type=ao and parent_id=region_id) or by the region org itself.
- Supports filtering by event type ids.
- Supports date window via start_date (required for large result sets; defaults to today UTC) and optional end_date.
- Results are ordered by start_date, id, org.name, start_time to match Slack home ordering.
- For aggregated “planned_qs” and per-user flags, prefer the specialized Calendar Home endpoint (#40).

Response 200:
```
{
  "results": [ {EventInstance...} ],
  "pagination": { "limit": 100, "offset": 0, "total": 123 }
}
```

---

## 40. Calendar Home Schedule (Aggregated)

GET /regions/{region_id}/calendar/home?ao_ids=1,2&event_type_ids=3,4&start_date=2025-01-01&open_q_only=false&my_events=false&limit=100&include=org,event_types,series

Purpose:
- Backs the Slack Home “Upcoming Schedule” view. Mirrors the SQL in special_queries.home_schedule_query and the filters built in features/calendar/home.py.

Query Params:
- ao_ids (CSV, optional): Filter to specific AO org_ids. If omitted and include_nearby=false, default is all AOs for the region.
- event_type_ids (CSV, optional)
- start_date (required for big lists; default = today UTC)
- open_q_only (bool, optional, default false): Only events with no Q/Co-Q planned.
- my_events (bool, optional, default false): Restrict to events where the caller is attending or Q (see per-user flags below). Requires auth user context.
- limit (int, optional, default 100, max 200)
- include (CSV, optional): org,event_types,series to expand related data.
- include_nearby (bool, optional, default false): include events from nearby regions (future; server may ignore initially).

Response 200:
```
{
  "results": [
    {
      "event": {EventInstance...},
      "org": {Org...},
      "event_types": [ {EventType...} ],
      "series": {Event...} | null,
      "planned_qs": "Name1,Name2" | null,
      "user_attending": 0 | 1,
      "user_q": 0 | 1
    }
  ],
  "pagination": { "limit": 100, "offset": 0, "total": 97 }
}
```

Notes:
- planned_qs aggregates Attendance where Attendance_x_AttendanceType.attendance_type_id IN [2,3] (Q/Co-Q) into a comma-separated list of User.f3_name.
- user_attending is 1 if the auth user has any Attendance for the event instance, else 0.
- user_q is 1 if the auth user is Q/Co-Q for the event instance, else 0.
- Server SHOULD efficiently implement with one pass aggregation like the current SQL.

Errors:
- 400 invalid_filter

---

## 41. List Attendance (Event Instance)

GET /event-instances/{event_instance_id}/attendance?types=q,co_q,attending

Purpose:
- Retrieve attendance records for an event instance, optionally filtered by type. Used by Slack UI to render current Q/Co-Q, attending, etc.

Query Params:
- types (CSV, optional): one or more of attending,q,co_q. If omitted, returns all.

Response 200:
```
{
  "event_instance_id": 222,
  "attendance": [
    {
      "user": { "id": 1, "f3_name": "Example" },
      "type": "q" | "co_q" | "attending"
    }
  ]
}
```

---

## 42. Upsert Attendance (Event Instance)

POST /event-instances/{event_instance_id}/attendance

Request JSON:
```
{
  "items": [
    { "user_id": 1, "type": "q" },
    { "user_id": 2, "type": "co_q" },
    { "user_id": 3, "type": "attending" }
  ],
  "replace_types": ["q","co_q"]   // optional; if provided, server replaces existing entries for these types
}
```

Behavior:
- Creates or updates Attendance rows and their Attendance_x_AttendanceType join based on type.
- Recommended server-side mapping:
  - q -> attendance_type_id = 2
  - co_q -> attendance_type_id = 3
  - attending -> attendance_type_id = 1 (example)
- If replace_types provided, server should remove any existing attendance entries of those types before inserting new ones.

Response 200:
```
{
  "event_instance_id": 222,
  "updated": 3
}
```

Errors:
- 400 invalid_type
- 404 event_instance_not_found

---

## 43. Remove Attendance (Event Instance)

DELETE /event-instances/{event_instance_id}/attendance

Request JSON:
```
{
  "user_id": 1,
  "type": "q" | "co_q" | "attending"
}
```

Response 200:
```
{ "deleted": 1 }
```

---

## 44. Assign Q / Co-Q (Convenience)

PUT /event-instances/{event_instance_id}/q

Purpose:
- Convenience wrapper over attendance upsert to match Slack “Assign Q” modal in home.py.

Request JSON:
```
{
  "q_user_id": 123,
  "co_q_user_ids": [456,789]
}
```

Response 200:
```
{
  "event_instance_id": 222,
  "q_user_id": 123,
  "co_q_user_ids": [456,789]
}
```

---

## 45. List Region Admins

GET /regions/{region_id}/admins

Purpose:
- Used by Slack to determine admin capabilities in the Home view.

Response 200:
```
{
  "results": [ { "user": {User...}, "slack_user": {SlackUser...} | null } ]
}
```

---

## 46. Add Region Admin

POST /regions/{region_id}/admins

Request JSON:
```
{ "user_id": 123 }
```

Behavior:
- Grants the user an admin Role for the region (Role_x_User_x_Org with Role.name = "admin").

Response 201:
```
{ "region_id": 111, "user_id": 123, "role": "admin" }
```

Errors:
- 404 region_not_found
- 404 user_not_found
- 409 already_admin

---

## 47. Remove Region Admin

DELETE /regions/{region_id}/admins/{user_id}

Behavior:
- Revokes the admin role assignment for the user in the region.

Response 200:
```
{ "region_id": 111, "user_id": 123, "removed": true }
```

---

## 48. List Positions and Assigned Users

GET /orgs/{org_id}/positions

Query Params:
- org_type_scope=auto|region|ao (optional, default auto): controls which positions are eligible based on Org_Type.

Response 200:
```
{
  "org_id": 999,
  "results": [
    {
      "position": {Position...},
      "users": [ {User...} ],
      "slack_users": [ {SlackUser...} ]
    }
  ]
}
```

---

## 49. Get User Permissions (By Org)

GET /users/{user_id}/permissions?org_id=123

Response 200:
```
{ "user_id": 1, "org_id": 123, "permissions": [ {Permission...} ] }
```

Notes:
- Mirrors utilities.database.special_queries.get_user_permission_list.

---

## 50. Update Region Profile

PATCH /regions/{region_id}

Purpose:
- Backed by `features/region.py` edit flow. Updates general Region (Org) metadata and optionally logo.

Request JSON (any subset):
```
{
  "name": "F3 Metro",
  "description": "The Queen City",
  "website": "https://f3metro.com",
  "email": "nantan@f3metro.com",
  "twitter": "@F3Metro",
  "facebook": "https://facebook.com/f3metro",
  "instagram": "@f3metro",
  "logo_file_id": "abc123"   // optional; resolves via /files to set Org.logo_url
}
```

Behavior:
- Validates URLs/emails format where provided.
- If `logo_file_id` provided, server resolves to URL and updates `logo_url` on Org.
- Does not change org_type or parent_id.

Response 200:
```
{Org...}
```

Errors:
- 404 region_not_found
- 400 validation_error

---

## 51. Get Region Settings

GET /regions/{region_id}/settings

Purpose:
- Returns the Slack-space settings blob used by config/welcome/custom fields/canvas.

Response 200:
```
{SlackSpace Settings...}
```

Notes:
- Sensitive fields like `email_password` MUST be masked (e.g., "***masked***").
- Clients should treat unknown keys as forward-compatible.

---

## 52. Update Region Settings

PATCH /regions/{region_id}/settings

Purpose:
- Partial update of settings. Used by `features/config.py` (general + email), `features/welcome.py`, `features/custom_fields.py`, and `features/calendar/config.py`.

Request JSON (any subset of Settings projection):
```
{
  "editing_locked": 1,
  "default_backblast_destination": "ao",
  "backblast_destination_channel": "C0123",
  "preblast_reminder_days": 2,
  "email_enabled": 1,
  "email_user": "example@gmail.com",
  "email_password": "plain-text-secret",   // server encrypts at rest; never returns plaintext on read
  "welcome_dm_enable": 1,
  "welcome_dm_template": "...",
  "welcome_channel_enable": 1,
  "welcome_channel": "C0WELCOME",
  "send_q_lineups": true,
  "special_events_enabled": true,
  "special_events_post_days": 7,
  "canvas_channel": "C0CANVAS"
}
```

Behavior:
- Only provided keys are updated within the JSONB settings object for the region’s SlackSpace.
- `email_password` is stored encrypted. On read, return masked value.
- Returns the merged settings document.

Response 200:
```
{SlackSpace Settings...}
```

Errors:
- 404 region_not_found
- 400 validation_error

---

## 53. List Custom Fields

GET /regions/{region_id}/custom-fields

Response 200:
```
{
  "results": [
    { "name": "Event Type", "type": "Dropdown", "options": ["Bootcamp"], "enabled": true }
  ]
}
```

Notes:
- Convenience wrapper over `GET /regions/{region_id}/settings` that returns only `custom_fields`.

---

## 54. Upsert Custom Field

POST /regions/{region_id}/custom-fields

Request JSON:
```
{
  "name": "Event Type",
  "type": "Dropdown" | "Text" | "Number",
  "options": ["Bootcamp","QSource"],    // required if type=Dropdown; ignored otherwise
  "enabled": true
}
```

Behavior:
- Inserts or replaces the named field in `settings.custom_fields`.
- If `type=Dropdown` and `options` missing/empty, return validation error.

Response 200:
```
{ "updated": 1 }
```

Errors:
- 400 validation_error
- 404 region_not_found

---

## 55. Update Custom Field

PATCH /regions/{region_id}/custom-fields/{field_name}

Request JSON (subset):
```
{ "name": "New Name", "type": "Text", "options": [], "enabled": false }
```

Response 200:
```
{ "updated": 1 }
```

Errors:
- 404 custom_field_not_found

---

## 56. Delete Custom Field

DELETE /regions/{region_id}/custom-fields/{field_name}

Response 200:
```
{ "deleted": 1 }
```

Errors:
- 404 custom_field_not_found

---

## 57. Create Position

POST /orgs/{org_id}/positions

Request JSON:
```
{ "name": "Nantan", "description": "Region lead" }
```

Behavior:
- Creates a Position owned by the org (region or AO).

Response 201:
```
{Position...}
```

Errors:
- 404 org_not_found
- 409 duplicate_name

---

## 58. Update Position

PATCH /positions/{position_id}

Request JSON (subset):
```
{ "name": "Weasel Shaker", "description": "Ops lead", "is_active": true }
```

Response 200:
```
{Position...}
```

Errors:
- 404 position_not_found
- 409 duplicate_name

---

## 59. Delete Position

DELETE /positions/{position_id}

Behavior:
- Soft delete or hard delete (implementation choice). If soft, return status deactivated.

Response 200:
```
{ "position_id": 77, "status": "deleted" }
```

Errors:
- 404 position_not_found

---

## 60. Assign Position to User

POST /orgs/{org_id}/positions/{position_id}/assign

Request JSON:
```
{ "user_id": 123 }
```

Behavior:
- Upserts a Position_x_Org_x_User record.

Response 201:
```
{ "org_id": 999, "position_id": 77, "user_id": 123 }
```

Errors:
- 404 org_not_found | position_not_found | user_not_found
- 409 already_assigned

---

## 61. Unassign Position from User

DELETE /orgs/{org_id}/positions/{position_id}/assign/{user_id}

Response 200:
```
{ "deleted": 1 }
```

Errors:
- 404 not_found

---

## 62. Set Region Admins (Replace)

PUT /regions/{region_id}/admins

Purpose:
- Convenience endpoint used by the Region form to set the full admin list in one call.

Request JSON:
```
{ "user_ids": [1,2,3] }
```

Behavior:
- Replaces all existing admin Role_x_User_x_Org rows for the region with the provided set.

Response 200:
```
{ "region_id": 111, "user_ids": [1,2,3] }
```

Errors:
- 404 region_not_found | user_not_found (if any invalid)

---

## 63. Trigger Canvas Rebuild

POST /regions/{region_id}/canvas/rebuild

Purpose:
- Triggers the server-side job that regenerates the Region Canvas content using the current settings and upcoming special events.

Request JSON (optional):
```
{ "force": true }
```

Response 202:
```
{ "status": "queued", "job_id": "uuid" }
```

Notes:
- Mirrors the `update_all_canvases` logic in `features/canvas.py` for a single region.

---

## 64. Get SlackSpace by Team

GET /slack-spaces/{team_id}

Purpose:
- Directly fetch the SlackSpace record by Slack team id. Useful for Slack interactivity backends where `team_id` is the primary identifier.

Response 200:
```
{ "team_id": "T0123", "org_id": 123, "settings": { … } }
```

Errors:
- 404 slackspace_not_found

---

## 65. Update SlackSpace Settings by Team

PATCH /slack-spaces/{team_id}/settings

Purpose:
- Alternative to region-scoped settings updates when the caller only has `team_id`.

Request/Response:
- Same as [52. Update Region Settings].

Security:
- Requires the same scopes as region settings and ownership verification for the Slack app installation.

---

## 66. Resolve User From Slack

POST /users/resolve-from-slack

Purpose:
- Convert a Slack user identity into the platform User/SlackUser, creating SlackUser mapping if missing. Mirrors `get_user()` usage in `features/user.py`.

Request JSON:
```
{ "slack_id": "U012345", "slack_team_id": "T012345" }
```

Behavior:
- Find SlackUser by (slack_id, slack_team_id). If not found but a matching User can be inferred via email or prior mapping rules, create the SlackUser link.

Response 200:
```
{ "user": {User...}, "slack_user": {SlackUser...} }
```

Errors:
- 404 not_found (if resolution is strictly required and cannot be inferred)

---

## 67. Get User

GET /users/{user_id}

Query Params:
- include=home_region (optional): expands `home_region_org` needed by the form initial values.

Response 200:
```
{User...}
```

Errors:
- 404 user_not_found

---

## 68. Update User

PATCH /users/{user_id}

Purpose:
- Backed by `handle_user_form` in `features/user.py` to update profile details and avatar.

Request JSON (any subset):
```
{
  "f3_name": "Short Circuit",
  "home_region_id": 123,
  "emergency_contact": "Jane Doe",
  "emergency_phone": "+1 555-123-4567",
  "emergency_notes": "…",
  "avatar_file_id": "abc123"   // optional; resolved to avatar_url via /files
}
```

Behavior:
- If `avatar_file_id` provided, server resolves to URL and updates `avatar_url`.
- Validates that `home_region_id` references an Org with org_type=region.

Response 200:
```
{User...}
```

Errors:
- 404 user_not_found | region_not_found
- 400 validation_error

---

## 69. Search Regions (Typeahead)

GET /regions/search?q=metro&limit=10

Purpose:
- Supports the ExternalSelectElement for "Home Region" in the user form.

Query Params:
- q (required): search string (name prefix/ILIKE match)
- limit (optional, default 10, max 25)

Response 200:
```
{ "results": [ { "id": 123, "name": "F3 Metro" } ] }
```

---

## 70. Get Slack User Mapping

GET /slack-users/by-slack?slack_id=U012345&slack_team_id=T012345

Purpose:
- Lightweight fetch for an existing SlackUser mapping when you already know the Slack ids.

Response 200:
```
{SlackUser...}
```

Errors:
- 404 slack_user_not_found

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
  "preblast_ts": "2025-01-19T20:15:00Z", // optional; set when posted
  "backblast_rich": { ... },
  "backblast": "<formatted text>",
  "backblast_ts": "2025-02-10T12:34:56Z",
  "pax_count": 17,
  "fng_count": 2,
  "meta": { "Weather": "Humid" }
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

## 71. List My Preblast Candidates

GET /regions/{region_id}/preblast/candidates?start_date=YYYY-MM-DD

Purpose:
- Mirrors the selection list in `build_event_preblast_select_form` used by `features/calendar/event_preblast.py`. Returns upcoming EventInstances where the caller is planned (Attendance.is_planned) and has type Q/Co-Q, and that have not yet been preblasted.

Query Params:
- start_date (optional; default = today in region TZ)

Response 200:
```
{
  "results": [ {EventInstance...} ]
}
```

Notes:
- Server infers the caller from auth context and filters Attendance for that user with AttendanceType in [2,3] and EventInstance.preblast_ts IS NULL, EventInstance.is_active = true, and within the region or its AOs.

---

## 72. Update Preblast Draft

PATCH /event-instances/{event_instance_id}/preblast

Purpose:
- Backed by `handle_event_preblast_edit`. Updates preblast fields, location, optional tag, and Q/Co-Q co-leads for the event instance.

Request JSON (subset):
```
{
  "name": "Title",
  "location_id": 456,
  "preblast_rich": { ... },
  "preblast": "<plain text>",
  "event_tag_id": 1011 | null,   // optional single tag
  "co_q_user_ids": [2,3]         // optional, replaces existing co-Qs as planned (is_planned=true)
}
```

Behavior:
- Updates EventInstance basic fields.
- If `event_tag_id` provided, replaces the single tag on the instance (deletes existing from EventTag_x_EventInstance and inserts new one). If null, clears tag.
- If `co_q_user_ids` provided, replaces existing co-Q attendance for this instance with the provided list (attendance_type_id=3, is_planned=true). Does not change the primary Q here; use Assign Q (#44) or include caller as Q in attendance upsert (#42).

Response 200:
```
{EventInstance...}
```

Errors:
- 404 event_instance_not_found
- 400 validation_error

---

## 73. Mark Preblast Posted

POST /event-instances/{event_instance_id}/preblast/posted

Purpose:
- Called when the preblast is posted to Slack. Persists the message ts and optionally the channel.

Request JSON:
```
{
  "preblast_ts": "2025-01-19T20:15:00Z" | "1737301234.567800",  // supports RFC3339 or Slack ts string
  "channel": "C0123" | null
}
```

Behavior:
- Sets EventInstance.preblast_ts and may store `meta.preblast_channel`.

Response 200:
```
{ "event_instance_id": 222, "preblast_ts": "1737301234.567800" }
```

Errors:
- 404 event_instance_not_found

---

## 74. Submit Backblast

POST /event-instances/{event_instance_id}/backblast

Purpose:
- Replaces the DbManager + Slack flow in `features/backblast.py::handle_backblast_post`. Creates or updates the EventInstance backblast content, attendance, counts, custom fields, and uploaded files metadata.

Request JSON:
```
{
  "title": "Workout Name",
  "date": "2025-02-10",
  "ao_id": 123,
  "event_type_id": 789,             // single event type id for now
  "q_user_id": 111,
  "co_q_user_ids": [222,333],
  "attendee_user_ids": [444,555],   // regular pax
  "down_range_user_ids": [666],     // optional DR pax
  "non_slack_pax": ["John Doe"],   // optional non-slack attendees
  "fng_names": ["Blue Steel"],     // optional
  "count": 12,                      // optional; if omitted, server may auto-calc
  "moleskin_rich": { ... },         // Slack rich text JSON
  "files": [                        // optional; uploaded/processed separately
    { "url": "https://...", "width": 1024, "height": 768, "mime_type": "image/jpeg" }
  ],
  "custom_fields": { "Weather": "Humid" }
}
```

Behavior:
- Updates EventInstance fields: name/title, start_date, org_id (ao), backblast_rich, backblast (plain), backblast_ts (now), pax_count, fng_count, meta (merge custom_fields), is_active=true.
- Upserts EventType_x_EventInstance to set the selected event type (single for now).
- Replaces Attendance with Q (type=2), Co-Qs (type=3), and Attending (type=1) according to lists, marking `is_planned=false`.
- Stores file metadata in `meta.files` or a related storage, depending on implementation; returns normalized file URLs.

Response 200:
```
{EventInstance...}
```

Errors:
- 400 validation_error
- 404 event_instance_not_found | ao_not_found | event_type_not_found | user_not_found

---

## 75. Search Users (Typeahead)

GET /users/search?q=short&region_id=123&limit=20

Purpose:
- Supports Slack multi-user selects for Q/Co-Q/PAX. Filters users by relevance to the region (e.g., Slack team membership or home_region).

Query Params:
- q (required)
- region_id (optional but recommended)
- limit (optional; default 20, max 50)

Response 200:
```
{ "results": [ { "id": 1, "f3_name": "Short Circuit", "avatar_url": "…" } ] }
```

---

## 76. Create SlackSpace

POST /slack-spaces

Purpose:
- Creates a SlackSpace record and seeds baseline settings. Mirrors `get_region_record` where a SlackSpace may be created on first contact.

Request JSON:
```
{
  "team_id": "T012345",
  "workspace_name": "F3 Example",
  "bot_token": "xoxb-...",         // optional; stored securely
  "settings": {                      // optional initial settings
    "team_id": "T012345",
    "workspace_name": "F3 Example"
  }
}
```

Response 201:
```
{ "team_id": "T012345", "settings": { … } }
```

Errors:
- 409 slackspace_exists

---

## 77. Connect SlackSpace to Org

POST /slack-spaces/{team_id}/connect-org

Purpose:
- Connects an existing SlackSpace to an Org via the `orgs_x_slack_spaces` table. Mirrors the local dev behavior in `get_region_record` and Org linkage.

Request JSON:
```
{ "org_id": 123 }
```

Response 200:
```
{ "team_id": "T012345", "org_id": 123 }
```

Errors:
- 404 slackspace_not_found | org_not_found
- 409 already_connected

---

## 78. Sync Slack Users

POST /slack-spaces/{team_id}/users/sync

Purpose:
- Imports Slack users into the platform, creating `User` and `SlackUser` records as needed. Mirrors `populate_users` and parts of `get_user`.

Request JSON (optional):
```
{ "org_id": 123 }   // optional: set home_region_id for created users
```

Behavior:
- Fetches users from Slack via the app installation for team_id.
- Upserts Users by email (or slack_id fallback) and SlackUsers by (slack_id, team_id).

Response 202:
```
{ "team_id": "T012345", "users_created": 42, "slack_users_created": 57 }
```

Errors:
- 404 slackspace_not_found
- 502 slack_api_error

---

## 79. List Slack Users (Team)

GET /slack-spaces/{team_id}/slack-users?q=short&limit=50

Purpose:
- Lists SlackUser records for a team, optional search by name/email. Mirrors cached usage in `update_local_slack_users` and selection flows.

Query Params:
- q (optional; search name/email)
- limit (optional; default 50, max 200)

Response 200:
```
{ "results": [ {SlackUser...} ] }
```

Errors:
- 404 slackspace_not_found

---

## 80. Migrate Slackblast Settings

POST /admin/migrate/slackblast-settings

Purpose:
- One-time migration to seed SlackSpace.settings from legacy Slackblast or Paxminer sources. Mirrors `migrate_slackblast_settings` behavior.

Request JSON:
```
{ "team_id": "T012345" }
```

Behavior:
- Attempts to load settings from the legacy Slackblast DB by team_id; falls back to Paxminer if needed.
- Converts/normalizes known JSON fields: backblast_moleskin_template, preblast_moleskin_template, welcome_dm_template, custom_fields.
- Stores merged settings into SlackSpace.settings.

Response 200:
```
{ "team_id": "T012345", "settings": { … } }
```

Errors:
- 404 slackspace_not_found
- 404 legacy_not_found

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
