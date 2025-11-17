import os
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Sponsor, Child, Donation, Update

app = FastAPI(title="Charity Sponsorship API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# Utility & Auth helpers
# -------------------------

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")

class AuthUser(BaseModel):
    id: str
    email: str

async def get_current_user(x_api_key: Optional[str] = Header(None)) -> AuthUser:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    sponsor = db["sponsor"].find_one({"api_key": x_api_key})
    if not sponsor:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return AuthUser(id=str(sponsor.get("_id")), email=sponsor.get("email"))

# -------------------------
# Basic
# -------------------------
@app.get("/")
def root():
    return {"message": "Charity Sponsorship API running"}

@app.get("/test")
def test_database():
    response = {"backend": "✅ Running", "database": "❌ Not Available"}
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["collections"] = db.list_collection_names()
    except Exception as e:
        response["database"] = f"Error: {str(e)[:80]}"
    return response

# -------------------------
# Auth: simple email signup/signin using API key (demo only)
# -------------------------
class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    country: Optional[str] = None

class SigninRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    api_key: str
    sponsor_id: str
    name: str

@app.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    # ensure email unique
    existing = db["sponsor"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    api_key = secrets.token_hex(16)
    # Simple hash placeholder (not secure). In production use bcrypt/argon2.
    password_hash = secrets.token_hex(8)  # do not store raw password in demo
    sponsor = Sponsor(
        name=payload.name,
        email=payload.email,
        password_hash=password_hash,
        country=payload.country,
        api_key=api_key,
    )
    sponsor_id = create_document("sponsor", sponsor)
    return AuthResponse(api_key=api_key, sponsor_id=sponsor_id, name=payload.name)

@app.post("/auth/signin", response_model=AuthResponse)
def signin(payload: SigninRequest):
    # demo: match by email only, return existing api key
    doc = db["sponsor"].find_one({"email": payload.email})
    if not doc:
        raise HTTPException(status_code=404, detail="Account not found")
    api_key = doc.get("api_key") or secrets.token_hex(16)
    if not doc.get("api_key"):
        db["sponsor"].update_one({"_id": doc["_id"]}, {"$set": {"api_key": api_key}})
    return AuthResponse(api_key=api_key, sponsor_id=str(doc["_id"]), name=doc.get("name", ""))

# -------------------------
# Children catalog and sponsorship
# -------------------------
class ChildCreate(BaseModel):
    name: str
    age: int
    country: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None

@app.post("/children")
def create_child(payload: ChildCreate, user: AuthUser = Depends(get_current_user)):
    child = Child(**payload.model_dump())
    child_id = create_document("child", child)
    return {"id": child_id}

@app.get("/children")
def list_children(country: Optional[str] = None, sponsored: Optional[bool] = None):
    query = {}
    if country:
        query["country"] = country
    if sponsored is not None:
        query["sponsored"] = sponsored
    docs = get_documents("child", query)
    # convert ids
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs

class SponsorRequest(BaseModel):
    child_id: str

@app.post("/sponsor")
def sponsor_child(payload: SponsorRequest, user: AuthUser = Depends(get_current_user)):
    child = db["child"].find_one({"_id": oid(payload.child_id)})
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if child.get("sponsored"):
        raise HTTPException(status_code=400, detail="Child already sponsored")
    db["child"].update_one({"_id": child["_id"]}, {"$set": {"sponsored": True, "sponsored_by": user.id}})
    return {"status": "ok"}

# -------------------------
# Donations (record only for demo)
# -------------------------
class DonationCreate(BaseModel):
    child_id: str
    amount: float
    currency: str = "USD"
    month: Optional[str] = None

@app.post("/donations")
def create_donation(payload: DonationCreate, user: AuthUser = Depends(get_current_user)):
    # Ensure sponsor owns child
    child = db["child"].find_one({"_id": oid(payload.child_id)})
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if child.get("sponsored_by") != user.id:
        raise HTTPException(status_code=403, detail="You do not sponsor this child")
    donation = Donation(sponsor_id=user.id, child_id=payload.child_id, amount=payload.amount, currency=payload.currency, month=payload.month, status="completed")
    donation_id = create_document("donation", donation)
    return {"id": donation_id}

@app.get("/donations")
def list_donations(user: AuthUser = Depends(get_current_user)):
    docs = get_documents("donation", {"sponsor_id": user.id})
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs

# -------------------------
# Updates for children
# -------------------------
class UpdateCreate(BaseModel):
    child_id: str
    title: str
    content: Optional[str] = None
    photo_url: Optional[str] = None

@app.post("/updates")
def create_update(payload: UpdateCreate, user: AuthUser = Depends(get_current_user)):
    # Ensure sponsor owns child to post an update (or allow any sponsor?). Here require owner.
    child = db["child"].find_one({"_id": oid(payload.child_id)})
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if child.get("sponsored_by") != user.id:
        raise HTTPException(status_code=403, detail="You do not sponsor this child")
    update_doc = Update(**payload.model_dump())
    update_id = create_document("update", update_doc)
    return {"id": update_id}

@app.get("/children/{child_id}/updates")
def list_updates(child_id: str, user: AuthUser = Depends(get_current_user)):
    # Only sponsor of the child can view updates
    child = db["child"].find_one({"_id": oid(child_id)})
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if child.get("sponsored_by") != user.id:
        raise HTTPException(status_code=403, detail="You do not sponsor this child")
    docs = get_documents("update", {"child_id": child_id})
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs

# -------------------------
# Dashboard data
# -------------------------
@app.get("/me")
def my_profile(user: AuthUser = Depends(get_current_user)):
    sponsor = db["sponsor"].find_one({"_id": oid(user.id)})
    if not sponsor:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Children count
    children = list(db["child"].find({"sponsored_by": user.id}))
    total_children = len(children)
    # Total donated
    donations = list(db["donation"].find({"sponsor_id": user.id}))
    total_donated = float(sum(d.get("amount", 0) for d in donations))
    # Convert ids
    for c in children:
        c["id"] = str(c.pop("_id"))
    for d in donations:
        d["id"] = str(d.pop("_id"))
    return {
        "id": user.id,
        "name": sponsor.get("name"),
        "email": sponsor.get("email"),
        "avatar_url": sponsor.get("avatar_url"),
        "children": children,
        "stats": {
            "children": total_children,
            "total_donated": total_donated,
        },
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
