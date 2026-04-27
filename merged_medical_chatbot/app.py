from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

import base64
import requests
import io
from PIL import Image
from dotenv import load_dotenv
import os
import logging

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from rag_utils import add_to_rag, build_context, load_medical_kb_to_rag

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="secret123")

templates = Jinja2Templates(directory="templates")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is not set in the .env file")

# ------------------- DATABASE -------------------

DATABASE_URL = "sqlite:///./users.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String)

    age = Column(String, default="")
    gender = Column(String, default="")
    blood_group = Column(String, default="")
    allergies = Column(String, default="")
    diseases = Column(String, default="")
    medications = Column(String, default="")
    emergency_contact = Column(String, default="")


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def call_groq(messages, max_tokens=1000):
    response = requests.post(
        GROQ_API_URL,
        json={
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": messages,
            "max_tokens": max_tokens
        },
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        timeout=45
    )

    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]


def format_sources(retrieved):
    formatted = []
    seen = set()

    for item in retrieved:
        source = item.get("source", "")
        filename = item.get("extra", {}).get("filename", "")
        section = item.get("extra", {}).get("section", "")
        key = (source, filename, section)

        if key in seen:
            continue
        seen.add(key)

        text = item.get("text", "") or ""
        short_text = text[:180] + "..." if len(text) > 180 else text

        formatted.append({
            "source": source,
            "text": short_text,
            "filename": filename,
            "section": section
        })

    return formatted


def get_medical_profile_text(username: str):
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.username == username).first()
        if not user:
            return "No profile found."

        return f"""
Age: {user.age or 'Not provided'}
Gender: {user.gender or 'Not provided'}
Blood Group: {user.blood_group or 'Not provided'}
Allergies: {user.allergies or 'Not provided'}
Existing Diseases: {user.diseases or 'Not provided'}
Current Medications: {user.medications or 'Not provided'}
Emergency Contact: {user.emergency_contact or 'Not provided'}
""".strip()
    finally:
        db_session.close()


# ------------------- ROUTES -------------------

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    if "user" not in request.session:
        return RedirectResponse(url="/")
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "username": request.session["user"]
        }
    )


# ------------------- AUTH -------------------

@app.post("/signup")
async def signup(username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return {"message": "User already exists"}

    new_user = User(username=username, password=password)
    db.add(new_user)
    db.commit()

    return {"message": "Signup successful"}


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db=Depends(get_db)):
    user = db.query(User).filter(User.username == username, User.password == password).first()

    if user:
        request.session["user"] = username
        return {"message": "Login successful"}

    return {"message": "Invalid credentials"}


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/guest")
async def guest_login(request: Request):
    request.session["user"] = "guest"
    return RedirectResponse(url="/chat")


# ------------------- MEDICAL PROFILE -------------------

@app.get("/medical_profile")
async def get_medical_profile(request: Request, db=Depends(get_db)):
    if "user" not in request.session:
        raise HTTPException(status_code=401, detail="Please login first")

    username = request.session["user"]
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "username": user.username,
        "age": user.age or "",
        "gender": user.gender or "",
        "blood_group": user.blood_group or "",
        "allergies": user.allergies or "",
        "diseases": user.diseases or "",
        "medications": user.medications or "",
        "emergency_contact": user.emergency_contact or ""
    }


@app.post("/medical_profile")
async def save_medical_profile(
    request: Request,
    age: str = Form(""),
    gender: str = Form(""),
    blood_group: str = Form(""),
    allergies: str = Form(""),
    diseases: str = Form(""),
    medications: str = Form(""),
    emergency_contact: str = Form(""),
    db=Depends(get_db)
):
    if "user" not in request.session:
        raise HTTPException(status_code=401, detail="Please login first")

    username = request.session["user"]
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.age = age
    user.gender = gender
    user.blood_group = blood_group
    user.allergies = allergies
    user.diseases = diseases
    user.medications = medications
    user.emergency_contact = emergency_contact

    db.commit()

    return {"message": "Medical profile saved successfully"}


# ------------------- LOAD MEDICAL KB -------------------

@app.get("/load_kb")
async def load_kb(request: Request):
    username = request.session.get("user", "guest")
    result = load_medical_kb_to_rag(username=username)
    return result


# ------------------- IMAGE + RAG -------------------

@app.post("/upload_and_query")
async def upload_and_query(
    request: Request,
    image: UploadFile = File(...),
    query: str = Form(...),
    symptoms: str = Form("")
):
    try:
        if "user" not in request.session:
            raise HTTPException(status_code=401, detail="Please login first")

        username = request.session["user"]
        medical_profile = get_medical_profile_text(username)
        image_content = await image.read()

        if not image_content:
            raise HTTPException(status_code=400, detail="Empty file")

        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid file type")

        if len(image_content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

        try:
            img = Image.open(io.BytesIO(image_content))
            img.verify()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

        encoded_image = base64.b64encode(image_content).decode("utf-8")
        mime_type = image.content_type or "image/jpeg"

        vision_messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI medical image assistant. "
                    "Describe only what can reasonably be observed from the image. "
                    "Do not provide a confirmed diagnosis. "
                    "Be cautious and say when uncertain."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
User question: {query}
Symptoms: {symptoms}
Medical Profile:
{medical_profile}

Analyze the uploaded medical image and return:
1. Key visual observations
2. Possible interpretation
3. Short safety note
"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        }
                    }
                ]
            }
        ]

        image_analysis = call_groq(vision_messages, max_tokens=700)

        combined_text = f"""
Question: {query}
Symptoms: {symptoms}
Medical Profile: {medical_profile}
Analysis: {image_analysis}
""".strip()

        add_to_rag(
            text=combined_text,
            username=username,
            source="image_analysis",
            extra={
                "filename": image.filename,
                "symptoms": symptoms,
                "question": query
            }
        )

        image_context, image_retrieved = build_context(
            query=query,
            username=username,
            top_k=3,
            source="image_analysis"
        )

        kb_context, kb_retrieved = build_context(
            query=query,
            username=username,
            top_k=3,
            source="medical_kb"
        )

        full_context = "\n\n".join(
            part for part in [image_context, kb_context] if part.strip()
        )

        all_sources = image_retrieved + kb_retrieved

        grounded_messages = [
            {
                "role": "system",
                "content": (
                    "You are a medical assistant for informational purposes only. "
                    "Use ONLY the provided context and medical profile. "
                    "Do not invent findings. "
                    "Do not provide a confirmed diagnosis. "
                    "If medical knowledge base context is available, use it carefully along with image observations. "
                    "All headings must be bold. "
                    "Leave spaces between sections."
                )
            },
            {
                "role": "user",
                "content": f"""
Context from this user's stored medical analyses and knowledge base:
{full_context}

Medical Profile:
{medical_profile}

Current question: {query}
Symptoms: {symptoms}

Respond EXACTLY like this:

**Observations**

(2-3 lines)


**Possible Interpretation**

(explain)


**Treatment / Care Suggestions**

(paragraph)


**Precautionary Measures**

(paragraph)


**When to Consult a Doctor**

(paragraph)


**Disclaimer**

(short)

End with:
"If you have more symptoms or need further clarification, feel free to ask and I will help you."
"""
            }
        ]

        final_answer = call_groq(grounded_messages, max_tokens=1000)

        return {
            "response": final_answer,
            "sources": format_sources(all_sources)
        }

    except HTTPException as he:
        raise he
    except requests.RequestException as e:
        logger.error(f"Groq API error: {str(e)}")
        raise HTTPException(status_code=502, detail="AI service error")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Something went wrong")


# ------------------- FOLLOW-UP CHAT -------------------

@app.post("/ask_followup")
async def ask_followup(
    request: Request,
    query: str = Form(...)
):
    try:
        if "user" not in request.session:
            raise HTTPException(status_code=401, detail="Please login first")

        username = request.session["user"]
        medical_profile = get_medical_profile_text(username)

        image_context, image_retrieved = build_context(
            query=query,
            username=username,
            top_k=3,
            source="image_analysis"
        )

        kb_context, kb_retrieved = build_context(
            query=query,
            username=username,
            top_k=3,
            source="medical_kb"
        )

        full_context = "\n\n".join(
            part for part in [image_context, kb_context] if part.strip()
        )

        if not full_context.strip():
            raise HTTPException(
                status_code=400,
                detail="No stored medical context found. Upload an image first or load the knowledge base."
            )

        all_sources = image_retrieved + kb_retrieved

        followup_messages = [
            {
                "role": "system",
                "content": (
                    "You are a medical assistant for informational purposes only. "
                    "Use ONLY the provided context and medical profile. "
                    "Do not invent findings. "
                    "Do not provide a confirmed diagnosis. "
                    "All headings must be bold. "
                    "Leave spaces between sections."
                )
            },
            {
                "role": "user",
                "content": f"""
Context:
{full_context}

Medical Profile:
{medical_profile}

Follow-up Question:
{query}

Respond EXACTLY like this:

**Answer**

(clear answer)


**Relevant Previous Context**

(short explanation)


**Precautionary Measures**

(paragraph)


**When to Consult a Doctor**

(paragraph)


**Disclaimer**

(short)

End with:
"If you have more symptoms or need further clarification, feel free to ask and I will help you."
"""
            }
        ]

        final_answer = call_groq(followup_messages, max_tokens=900)

        return {
            "response": final_answer,
            "sources": format_sources(all_sources)
        }

    except HTTPException as he:
        raise he
    except requests.RequestException as e:
        logger.error(f"Groq API error: {str(e)}")
        raise HTTPException(status_code=502, detail="AI service error")
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Something went wrong")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)