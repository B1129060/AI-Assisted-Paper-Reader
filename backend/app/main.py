from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import upload, papers, overview, translation, paragraphs, highlights

from app.models.paper import Paper
from app.models.paragraph import Paragraph
from app.models.paper_overview import PaperOverview
from app.models.highlight import TextHighlight, PdfHighlight

app = FastAPI(title="Paper Reader MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(upload.router)
app.include_router(papers.router)
app.include_router(overview.router)
app.include_router(translation.router)
app.include_router(paragraphs.router)
app.include_router(highlights.router)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/")
def root():
    return {"message": "Paper Reader API is running"}