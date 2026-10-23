import os
import re
import uuid
import logging
from datetime import date, datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import create_engine, String, Date, DateTime, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, sessionmaker

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("carecloud-agent")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./patients.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Patient(Base):
    __tablename__ = "patients"
    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[str] = mapped_column(String(30), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True)
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    address_line_2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)
    insurance_provider: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    insurance_member_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(50), nullable=False, default="English")
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

Base.metadata.create_all(engine)

class PatientIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    date_of_birth: date
    sex: str
    phone_number: str
    email: Optional[EmailStr] = None
    address_line_1: str = Field(min_length=1, max_length=200)
    address_line_2: Optional[str] = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str
    zip_code: str
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: str = "English"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v):
        if not re.fullmatch(r"[A-Za-z][A-Za-z '\\-]{0,49}", v):
            raise ValueError("Use letters, spaces, hyphens or apostrophes for names")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v):
        if v > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return v

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        normalized = v.strip().title()
        allowed = {"Male", "Female", "Other", "Decline To Answer"}
        if normalized not in allowed:
            raise ValueError("sex must be Male, Female, Other, or Decline to Answer")
        return "Decline to Answer" if normalized == "Decline To Answer" else normalized

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Phone number must be a valid US 10-digit number")
        return digits

    @field_validator("state")
    @classmethod
    def validate_state(cls, v):
        states = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
        v = v.upper()
        if v not in states:
            raise ValueError("state must be a valid 2-letter US state abbreviation")
        return v

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, v):
        if not re.fullmatch(r"\d{5}(?:-\d{4})?", v):
            raise ValueError("ZIP must be 5 digits or ZIP+4")
        return v

class PatientUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_member_id: Optional[str] = None
    preferred_language: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def envelope(data=None, error=None):
    return {"data": data, "error": error}

def patient_dict(p: Patient):
    return {
        "patient_id": p.patient_id, "first_name": p.first_name, "last_name": p.last_name,
        "date_of_birth": p.date_of_birth.isoformat(), "sex": p.sex, "phone_number": p.phone_number,
        "email": p.email, "address_line_1": p.address_line_1, "address_line_2": p.address_line_2,
        "city": p.city, "state": p.state, "zip_code": p.zip_code,
        "insurance_provider": p.insurance_provider, "insurance_member_id": p.insurance_member_id,
        "preferred_language": p.preferred_language, "emergency_contact_name": p.emergency_contact_name,
        "emergency_contact_phone": p.emergency_contact_phone,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }

app = FastAPI(title="CareCloud Voice AI Patient Registration", version="1.0.0",
              description="Patient registration API for the Voice AI take-home assessment.")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    with open("app/static/index.html", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
def health():
    return envelope({"status": "ok"})

@app.get("/patients")
def list_patients(last_name: Optional[str] = None, date_of_birth: Optional[date] = None,
                  phone_number: Optional[str] = None, db: Session = Depends(get_db)):
    stmt = select(Patient).where(Patient.deleted_at.is_(None))
    if last_name:
        stmt = stmt.where(Patient.last_name.ilike(f"%{last_name.strip()}%"))
    if date_of_birth:
        stmt = stmt.where(Patient.date_of_birth == date_of_birth)
    if phone_number:
        digits = re.sub(r"\D", "", phone_number)
        if len(digits) == 11 and digits.startswith("1"): digits = digits[1:]
        stmt = stmt.where(Patient.phone_number == digits)
    patients = db.scalars(stmt.order_by(Patient.created_at.desc())).all()
    return envelope([patient_dict(p) for p in patients])

@app.get("/patients/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.deleted_at:
        raise HTTPException(404, detail=envelope(error="Patient not found"))
    return envelope(patient_dict(p))

@app.post("/patients", status_code=201)
def create_patient(payload: PatientIn, db: Session = Depends(get_db)):
    # Bonus: report likely duplicates so the caller/operator can choose update.
    existing = db.scalar(select(Patient).where(Patient.phone_number == payload.phone_number, Patient.deleted_at.is_(None)))
    if existing:
        raise HTTPException(409, detail=envelope(error={
            "message": "A patient with this phone number already exists",
            "existing_patient": patient_dict(existing)
        }))
    p = Patient(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    logger.info("PATIENT_CREATED %s", patient_dict(p))
    return envelope(patient_dict(p))

@app.put("/patients/{patient_id}")
def update_patient(patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.deleted_at:
        raise HTTPException(404, detail=envelope(error="Patient not found"))
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            setattr(p, key, value)
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(p)
    logger.info("PATIENT_UPDATED %s", p.patient_id)
    return envelope(patient_dict(p))

@app.delete("/patients/{patient_id}")
def soft_delete_patient(patient_id: str, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.deleted_at:
        raise HTTPException(404, detail=envelope(error="Patient not found"))
    p.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return envelope({"patient_id": p.patient_id, "deleted": True})

# Optional shared-secret protection for deployment; set APP_API_KEY and send X-API-Key.
@app.post("/voice/create_patient", status_code=201)
def voice_create_patient(payload: PatientIn, db: Session = Depends(get_db), x_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("APP_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, detail=envelope(error="Invalid API key"))
    return create_patient(payload, db)

@app.get("/dashboard-data", include_in_schema=False)
def dashboard_data(db: Session = Depends(get_db)):
    patients = db.scalars(select(Patient).where(Patient.deleted_at.is_(None)).order_by(Patient.created_at.desc())).all()
    return envelope([patient_dict(p) for p in patients])
