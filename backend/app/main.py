from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(title="SAP O2C Graph AI API", version="1.0.0")

# Allow React/Next.js frontend to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to localhost:3000 in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "SAP O2C Graph API with Groq is running smoothly!"}