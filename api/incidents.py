"""
RAKSHA-FORCE — Incident Reports API
─────────────────────────────────────
POST  /api/incidents           → Create incident report
GET   /api/incidents           → List incidents (filters supported)
GET   /api/incidents/{id}      → Get single incident with messages
PATCH /api/incidents/{id}      → Update status / priority (admin)

─── Example: Create Incident ──────────────────────────────────────────────────

POST /api/incidents
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "emergency_type": "fire",
  "description": "Large fire at Shivajinagar market, multiple shops burning",
  "reporter_name": "Rajesh Kumar",
  "phone": "9876543210",
  "location": "Shivajinagar Market, Pune",
  "latitude": 18.5289,
  "longitude": 73.8469
}

→ 201 Created
{
  "success": true,
  "incident_id": "uuid...",
  "priority": 2,
  "priority_label": "HIGH",
  "duplicate_of": null,
  "message": "Report submitted. Ref: INC-1234"
}

─── Example: List Incidents ───────────────────────────────────────────────────

GET /api/incidents?status=pending&priority=1&limit=20
Authorization: Bearer <admin-jwt>

→ 200 OK
{
  "incidents": [...],
  "total": 5,
  "filters_applied": { "status": "pending", "priority": 1 }
}
"""

from fastapi import FastAPI, HTTPException, Request, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from api.utils.auth import optional_auth, require_auth, require_role
from api.utils.db import db_error_response, get_client
from api.utils.geo import validate_coordinates
from api.utils.logger import get_logger
from api.utils.rate_limit import incident_limiter

# ── App ────────────────────────────────────────────────────────

app = FastAPI(title="RAKSHA-FORCE Incidents API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

log = get_logger("incidents")

# ── Constants ──────────────────────────────────────────────────

VALID_TYPES = {
    # Civic categories (Urban 360)
    "roads", "waste", "water", "drainage", "streetlights",
    "sanitation", "parks", "infrastructure", "traffic_signs", "encroachment",
    # Legacy emergency categories (for backward compatibility)
    "fire", "medical", "police", "ambulance", "fire_brigade",
    "accident", "flood", "women", "child", "missing", "other",
}

VALID_STATUSES = {
    "pending", "assigned", "on_the_way", "resolved",
    "submitted", "under_review", "in_progress", "blocked",
    "resolution_submitted", "awaiting_verification", "rejected", "reopened",
}

# Priority auto-calculation weights
TYPE_PRIORITY_MAP = {
    # Civic priorities
    "water":          1,  # Critical infrastructure
    "flood":          1,
    "fire":           1,
    "medical":        1,
    "ambulance":      1,
    "roads":          2,  # High impact / safety
    "drainage":       2,
    "accident":       2,
    "infrastructure": 2,
    "fire_brigade":   2,
    "women":          2,
    "child":          2,
    "waste":          3,  # Medium
    "streetlights":   3,
    "traffic_signs":  3,
    "sanitation":     3,
    "police":         3,
    "missing":        3,
    "parks":          4,  # Routine maintenance
    "encroachment":   4,
    "other":          3,
}

PRIORITY_LABELS = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM", 4: "LOW"}

# Keywords that escalate priority
CRITICAL_KEYWORDS = {
    "fire", "burning", "dead", "dying", "unconscious", "knife", "gun",
    "explosion", "bomb", "child", "baby", "flood", "collapse", "crush",
    # Civic hazard keywords
    "cave-in", "burst", "overflow", "sinkhole", "hazard", "danger",
    "sparking", "contamination", "blocked", "live wire", "flooding",
}


# ── Schemas ────────────────────────────────────────────────────

class IncidentCreateRequest(BaseModel):
    model_config = {"extra": "ignore"}

    emergency_type: str          = Field(..., description="Incident category / Civic service type")
    title:          str | None   = Field("", max_length=200)
    description:    str | None   = Field("", max_length=2000)
    reporter_name:  str | None   = Field("", max_length=200)
    phone:          str | None   = Field("", max_length=20)
    location:       str | None   = Field("", max_length=500, description="Human-readable address")
    latitude:       float        = Field(..., ge=-90,  le=90)
    longitude:      float        = Field(..., ge=-180, le=180)
    image_url:      str | None   = Field(None, max_length=2000)
    priority:       int | None   = Field(None, ge=1, le=4)
    status:         str | None   = Field(None)
    user_id:        str | None   = Field(None)

    @field_validator("emergency_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in VALID_TYPES:
            raise ValueError(
                f"Invalid emergency_type. Must be one of: {', '.join(sorted(VALID_TYPES))}"
            )
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return ""
        digits = "".join(c for c in v if c.isdigit())
        if digits and len(digits) < 6:
            raise ValueError("Phone number too short.")
        return v.strip()


class IncidentUpdateRequest(BaseModel):
    model_config = {"extra": "ignore"}

    status:                   str | None = Field(None)
    priority:                 int | None = Field(None, ge=1, le=4)
    assigned_team_id:         str | None = Field(None)
    resolution_notes:         str | None = Field(None)
    resolution_evidence_url:  str | None = Field(None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(VALID_STATUSES)}")
        return v


# ── Handlers ───────────────────────────────────────────────────

@app.post("/api/incidents/upload")
async def upload_incident_image(request: Request, file: UploadFile | None = File(None)):
    """
    Upload an incident image to Supabase Storage (incident-images bucket).
    Accepts multipart/form-data with 'file', or JSON with 'image_base64'.
    Returns persistent public URL.
    """
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/jpg", "image/webp"}
    MAX_SIZE = 5 * 1024 * 1024  # 5MB

    import uuid, re, os, base64

    content_bytes = b""
    content_type = "image/jpeg"
    file_name = "incident_image"

    if file is not None and file.filename:
        file_name = file.filename
        content_type = (file.content_type or "image/jpeg").lower()
        if content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format '{content_type}'. Allowed: JPG, PNG, WebP."
            )
        try:
            content_bytes = await file.read()
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read uploaded file data.")
    else:
        # Fallback to JSON body with base64 data
        try:
            body = await request.json()
            raw_b64 = body.get("image_base64") or body.get("file")
            if not raw_b64:
                raise HTTPException(status_code=400, detail="No file or image_base64 provided.")
            if "," in raw_b64:
                header, raw_b64 = raw_b64.split(",", 1)
                if "image/png" in header:
                    content_type = "image/png"
                elif "image/webp" in header:
                    content_type = "image/webp"
                else:
                    content_type = "image/jpeg"
            content_bytes = base64.b64decode(raw_b64)
            file_name = body.get("filename") or "incident.jpg"
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid upload data: {str(e)}")

    if len(content_bytes) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Image size exceeds 5MB limit.")

    ext = os.path.splitext(file_name)[1].lower()
    if not ext or ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".png" if "png" in content_type else ".webp" if "webp" in content_type else ".jpg"

    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", os.path.splitext(file_name)[0])[:30]
    storage_path = f"incidents/{uuid.uuid4().hex}_{clean_name}{ext}"

    sb = get_client()
    try:
        sb.storage.from_("incident-images").upload(
            storage_path,
            content_bytes,
            {"content-type": content_type, "upsert": "false"}
        )
        public_url = sb.storage.from_("incident-images").get_public_url(storage_path)
    except Exception as e:
        log.error("Image upload to Supabase storage failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(e)}")

    return {
        "success": True,
        "url": public_url,
        "path": storage_path,
        "filename": file_name,
    }


@app.post("/api/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident(request: Request):
    """
    Submit a new incident report / civic complaint.
    - Auth optional (demo users & anonymous reports allowed)
    - Auto-calculates priority from emergency_type + description keywords
    - Performs duplicate detection (same type within 200m in last 30 minutes)
    - Rate limited: 20 per minute per user/IP
    """
    client_ip = request.client.host or "unknown"
    user      = optional_auth(request)
    rate_key  = user.user_id if user else client_ip
    allowed, retry_after = incident_limiter.check(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Wait {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    try:
        payload = IncidentCreateRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    sb = get_client()

    # Calculate priority
    if payload.priority and 1 <= payload.priority <= 4:
        priority = payload.priority
    else:
        priority = _auto_priority(payload.emergency_type, payload.description or "")

    # Duplicate detection
    duplicate_id = _check_duplicate(sb, payload)

    # Determine user_id association
    resolved_user_id = user.user_id if user else (payload.user_id if payload.user_id else None)

    # Build record
    record = {
        "user_id":        resolved_user_id,
        "emergency_type": payload.emergency_type,
        "title":          payload.title or (payload.description[:60] if payload.description else ""),
        "description":    payload.description or "",
        "reporter_name":  payload.reporter_name or "",
        "phone":          payload.phone or "",
        "location":       payload.location or "",
        "latitude":       payload.latitude,
        "longitude":      payload.longitude,
        "status":         "pending",
        "priority":       priority,
        "image_url":      payload.image_url or None,
        "duplicate_of":   duplicate_id,
    }

    try:
        result = sb.table("incident_reports").insert(record).execute()
    except Exception as e:
        err_str = str(e).lower()
        # Fallback if user_id violated FK
        if record.get("user_id") and ("foreign key" in err_str or "uuid" in err_str):
            record["user_id"] = None
            try:
                result = sb.table("incident_reports").insert(record).execute()
            except Exception as e2:
                log.error("Incident insert retry failed", error=str(e2))
                raise HTTPException(status_code=500, detail="Database operation failed. Please try again.")
        else:
            log.error("Incident insert failed", error=str(e))
            raise HTTPException(status_code=500, detail="Database operation failed. Please try again.")

    incident = result.data[0] if result.data else {}
    inc_id   = incident.get("id", "unknown")

    log.info(
        "Incident created",
        incident_id=inc_id,
        type=payload.emergency_type,
        priority=priority,
        duplicate_of=duplicate_id,
        user_id=record.get("user_id"),
        has_image=bool(record.get("image_url")),
    )

    return {
        "success":        True,
        "incident_id":    inc_id,
        "incident":       incident,
        "priority":       priority,
        "priority_label": PRIORITY_LABELS.get(priority, "UNKNOWN"),
        "duplicate_of":   duplicate_id,
        "message":        f"Report submitted. Ref: INC-{inc_id[:8].upper()}",
    }


@app.get("/api/incidents")
async def list_incidents(request: Request):
    """
    List incident reports.
    Query params:
      status   (pending|assigned|on_the_way|resolved)
      type     (roads|waste|water|...)
      priority (1-4)
      limit    (default 50, max 200)
      userId   (filter by user_id)
      reporter_name (filter by reporter name)
      my       (true → only current user's incidents)
    """
    user   = optional_auth(request)
    params = dict(request.query_params)
    limit  = min(int(params.get("limit", 50)), 200)

    sb = get_client()
    try:
        q = (
            sb.table("incident_reports")
            .select("*, assignments(team_id, eta_minutes, assigned_at)")
            .order("priority", desc=False)
            .order("created_at", desc=True)
            .limit(limit)
        )

        # Citizens see only their own incidents if authenticated
        if user and user.is_citizen():
            q = q.eq("user_id", user.user_id)
        elif params.get("userId") or params.get("user_id"):
            q = q.eq("user_id", params.get("userId") or params.get("user_id"))
        elif params.get("reporter_name"):
            q = q.ilike("reporter_name", f"%{params.get('reporter_name')}%")

        if params.get("status"):
            q = q.eq("status", params["status"])
        if params.get("type"):
            q = q.eq("emergency_type", params["type"])
        if params.get("priority"):
            try:
                q = q.eq("priority", int(params["priority"]))
            except ValueError:
                pass

        result = q.execute()
    except Exception as e:
        log.error("Incident list failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch incidents.")

    applied = {k: v for k, v in params.items() if k in ("status", "type", "priority", "userId", "reporter_name")}
    return {
        "incidents":       result.data,
        "total":           len(result.data),
        "filters_applied": applied,
    }



@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str, request: Request):
    """
    Get a single incident by ID, including its chat messages.
    Admins see all; citizens see only their own; demo users see all.
    """
    user = optional_auth(request)
    sb   = get_client()

    try:
        result = (
            sb.table("incident_reports")
            .select("*")
            .eq("id", incident_id)
            .single()
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail="Incident not found.")

    incident = result.data
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    # Citizens can only view their own
    if user and user.is_citizen() and incident.get("user_id") != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Fetch messages
    try:
        msgs = (
            sb.table("incident_messages")
            .select("*")
            .eq("incident_id", incident_id)
            .order("created_at")
            .execute()
        )
        incident["messages"] = msgs.data
    except Exception:
        incident["messages"] = []

    # Fetch assignment
    try:
        assign = (
            sb.table("assignments")
            .select("*, teams(name, type, status)")
            .eq("incident_id", incident_id)
            .maybe_single()
            .execute()
        )
        incident["assignment"] = assign.data
    except Exception:
        incident["assignment"] = None

    return incident


@app.patch("/api/incidents/{incident_id}")
async def update_incident(incident_id: str, request: Request):
    """
    Update incident status or priority — Admin only.

    Example:
      PATCH /api/incidents/<uuid>
      { "status": "resolved" }
    """
    user = require_auth(request)
    require_role(user, "admin", "officer", "administrator")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    try:
        update = IncidentUpdateRequest(**body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    patch = {k: v for k, v in update.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="No fields to update.")

    patch["updated_at"] = _now_iso()

    sb = get_client()
    try:
        sb.table("incident_reports").update(patch).eq("id", incident_id).execute()
    except Exception as e:
        log.error("Incident update failed", incident_id=incident_id, patch=patch, error=str(e), repr=repr(e))
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")

    log.info("Incident updated", incident_id=incident_id, patch=patch, admin=user.user_id)
    return {"success": True, "incident_id": incident_id, "updated": patch}


# ── Internal helpers ───────────────────────────────────────────

def _auto_priority(emergency_type: str, description: str) -> int:
    """
    Auto-calculate priority (1=critical, 4=low) from type and keywords.
    """
    base = TYPE_PRIORITY_MAP.get(emergency_type, 3)

    # Escalate if critical keywords found in description
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in CRITICAL_KEYWORDS):
        base = max(1, base - 1)   # escalate one level

    return base


def _check_duplicate(sb, payload: IncidentCreateRequest) -> str | None:
    """
    Detect a likely duplicate: same emergency_type within ~300m in last 30 min.
    Uses bounding-box pre-filter (fast) then Haversine refinement.

    Returns the ID of the original incident, or None.
    """
    from datetime import datetime, timedelta, timezone
    from api.utils.geo import haversine_distance

    DUPLICATE_RADIUS_KM = 0.3   # 300 metres
    DUPLICATE_WINDOW_MIN = 30

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_WINDOW_MIN)).isoformat()

    try:
        # Bounding box: ±0.005° ≈ ±550m (generous pre-filter)
        delta = 0.005
        result = (
            sb.table("incident_reports")
            .select("id, latitude, longitude")
            .eq("emergency_type", payload.emergency_type)
            .neq("status", "resolved")
            .gte("created_at", cutoff)
            .gte("latitude",  payload.latitude  - delta)
            .lte("latitude",  payload.latitude  + delta)
            .gte("longitude", payload.longitude - delta)
            .lte("longitude", payload.longitude + delta)
            .limit(10)
            .execute()
        )
        for row in result.data or []:
            dist = haversine_distance(
                payload.latitude, payload.longitude,
                row["latitude"],  row["longitude"],
            )
            if dist <= DUPLICATE_RADIUS_KM:
                return row["id"]
    except Exception:
        pass  # Duplicate check is best-effort; never block submission

    return None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── Vercel handler ─────────────────────────────────────────────
handler = app
