from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from io import BytesIO
import datetime
import os

from app.core.dependencies import get_current_user

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def generate_ref_no():
    bs_year = datetime.date.today().year - 57
    result = (
        supabase.table("referrals")
        .select("id", count="exact")
        .execute()
    )
    seq = (result.count or 0) + 1
    return f"REF-{bs_year}-{seq:05d}"


def build_pdf(referral, doctor, from_fac, to_fac):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=40, bottomMargin=40, leftMargin=50, rightMargin=50)
    styles = getSampleStyleSheet()
    story = []

    # Header
    story.append(Paragraph("<b>Government of Nepal</b>", styles["Title"]))
    story.append(Paragraph(f"<b>{from_fac['name']}</b>", styles["Heading2"]))
    story.append(Paragraph(f"{from_fac['district']} District — Ministry of Health and Population", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Ref No
    story.append(Paragraph(f"<b>Referral Letter</b> Ref No: {referral['ref_no']}", styles["Heading1"]))
    story.append(Spacer(1, 12))

    # Patient details table
    patient_data = [
        ["Patient Name", referral["patient_name"], "Age/Sex", f"{referral['patient_age']} / {referral['patient_sex']}"],
        ["Contact", referral.get("patient_contact", "—"), "", ""],
    ]
    patient_table = Table(patient_data, colWidths=[100, 200, 80, 100])
    patient_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    story.append(patient_table)
    story.append(Spacer(1, 12))

    # Facilities
    story.append(Paragraph(f"<b>Referring Facility:</b> {from_fac['name']} ({from_fac['type']}, {from_fac['district']})", styles["Normal"]))
    story.append(Paragraph(f"<b>Receiving Facility:</b> {to_fac['name']} ({to_fac['type']}, {to_fac['district']})", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Clinical details – use a simple table for better layout
    clinical_data = [
        ["Diagnosis", referral.get("diagnosis", "—")],
        ["Reason for Referral", referral.get("reason_for_referral", "—")],
        ["Investigations Done", referral.get("investigations_done", "—")],
        ["Treatment Given", referral.get("treatment_given", "—")],
        ["Urgency", referral.get("urgency", "routine").upper()],
    ]
    clinical_table = Table(clinical_data, colWidths=[100, 380])
    clinical_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    story.append(clinical_table)
    story.append(Spacer(1, 12))

    # Doctor & date
    from datetime import datetime
    story.append(Paragraph(f"<b>Referring Doctor:</b> Dr. {doctor.get('full_name', 'N/A')}", styles["Normal"]))
    story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()

# ── LIST (must be before /{id}/pdf so FastAPI doesn't swallow it) ──────────

@router.get("/")
async def list_referrals(
    patient_id: str,
    user=Depends(get_current_user),
):
    """List referrals for a patient with facility details and fresh signed PDF URLs."""
    result = (
        supabase.table("referrals")
        .select(
            "*, "
            "to_facility:facilities!referrals_to_facility_id_fkey(id, name, type, district)"
        )
        .eq("patient_id", patient_id)
        .order("created_at", desc=True)
        .execute()
    )

    rows = result.data or []
    for row in rows:
        if row.get("pdf_path"):
            try:
                signed = (
                    supabase.storage
                    .from_("referral-letters")
                    .create_signed_url(row["pdf_path"], 3600)
                )
                row["pdf_url"] = signed.get("signedURL") or signed.get("signed_url")
            except Exception:
                row["pdf_url"] = None
        else:
            row["pdf_url"] = None

    return rows


# ── CREATE ──────────────────────────────────────────────────────────────────

@router.post("/")
async def create_referral(
    payload: dict,
    user=Depends(get_current_user),
):
    ref_no = generate_ref_no()
    payload["ref_no"] = ref_no
    payload["doctor_id"] = user["id"]
    # patient_id arrives from the Flutter payload; ensure it's present
    if "patient_id" not in payload:
        raise HTTPException(status_code=400, detail="patient_id is required")

    result = supabase.table("referrals").insert(payload).execute()
    referral = result.data[0]

    doctor = (
        supabase.table("user_profiles")
        .select("*")
        .eq("id", user["id"])
        .single()
        .execute()
        .data
    )
    from_fac = (
        supabase.table("facilities")
        .select("*")
        .eq("id", payload["from_facility_id"])
        .single()
        .execute()
        .data
    )
    to_fac = (
        supabase.table("facilities")
        .select("*")
        .eq("id", payload["to_facility_id"])
        .single()
        .execute()
        .data
    )

    pdf_bytes = build_pdf(referral, doctor, from_fac, to_fac)
    storage_path = f"{ref_no}.pdf"

    supabase.storage.from_("referral-letters").upload(
        storage_path,
        pdf_bytes,
        {"content-type": "application/pdf"},
    )
    supabase.table("referrals").update({"pdf_path": storage_path}).eq(
        "id", referral["id"]
    ).execute()

    signed = (
        supabase.storage
        .from_("referral-letters")
        .create_signed_url(storage_path, 3600)
    )

    return {
        "id": referral["id"],
        "ref_no": ref_no,
        "pdf_url": signed.get("signedURL") or signed.get("signed_url"),
    }


# ── PDF URL ─────────────────────────────────────────────────────────────────

@router.get("/{id}/pdf")
async def get_pdf(
    id: str,
    user=Depends(get_current_user),
):
    row = (
        supabase.table("referrals")
        .select("pdf_path")
        .eq("id", id)
        .single()
        .execute()
        .data
    )
    if not row or not row.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF not found")

    signed = (
        supabase.storage
        .from_("referral-letters")
        .create_signed_url(row["pdf_path"], 3600)
    )
    return {"pdf_url": signed.get("signedURL") or signed.get("signed_url")}