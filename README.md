# AI-Assisted-Paper-Reader


An AI-assisted academic paper reading system for PDF-based paper parsing, summarization, translation, manual correction, and highlight-supported review.

---

## Project Overview

This project aims to reduce the difficulty of reading academic papers by combining PDF parsing, paragraph extraction, summary generation, translation, PDF-to-text alignment, and user-side manual correction.

The system allows users to:
- upload and read academic paper PDFs,
- view extracted paragraph content side by side with the original PDF,
- edit incorrect extracted results,
- regenerate summaries and overview content,
- and add highlights to both generated text and PDF regions.

---

## Objectives

- Upload PDF papers
- Extract paragraph-level content
- Generate paragraph summaries and key points
- Provide Chinese translation
- Generate section summaries and paper overview
- Display extracted content and original PDF side by side
- Support paragraph and bullet-list editing
- Support text and PDF highlights


---

## Current Features

- PDF upload and parsing
- Paragraph and bullet-list extraction
- Paragraph summary generation
- Section summary generation
- Paper overview generation
- Chinese translation support
- PDF-to-text location mapping
- Paragraph editing
- Bullet-list editing
- Insert and delete paragraph functions
- Text highlight support
- PDF highlight support

---

## System Architecture

- **Frontend:** React + TypeScript + Vite
- **Backend:** FastAPI
- **Database:** PostgreSQL
- **Core Modules:** PDF parsing, paragraph processing, summarization, translation, overview regeneration, highlight management

---

## Repository Structure

```text
.
├─ backend/         # FastAPI backend source code
├─ frontend/        # React frontend source code
├─ docs/            # project documents and notes
├─ presentations/   # proposal, midterm, final slides
├─ assets/          # screenshots, diagrams, images
├─ samples/         # sample papers or outputs
└─ README.md
```

---

## Installation

### Backend
```text
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
### Frontend
```text
cd frontend
npm install
npm run dev
```
### Database

Please set up PostgreSQL first and configure the database connection before running the backend server.


---

## Usage

1. Start the backend and frontend servers.


2. Upload a paper PDF.


3. Wait for the system to parse and generate reading results.


4. Review extracted text, summaries, and translations.


5. Compare the extracted results with the original PDF.


6. Edit paragraphs or bullet lists if needed.


7. Regenerate the overview after major content changes.


8. Add highlights on generated text or PDF regions for review.




---

## Development Status

This repository is under active development as a senior project.

### Completed

- frontend-backend system setup

- database integration

- PDF upload and parsing

- paragraph extraction

- summary and overview generation

- translation support

- paragraph editing

- text and PDF highlighting


### In Progress

- user account and login system

- Inproving the text-to -speech reading system

- Evaluating a local file-based storage system as a lightweight alternative to part of the database workflow



---

## Screenshots

Screenshots and demo materials will be added in future updates.


---

## Team

劉曉帆 / B1129060




---

Advisor

李季青教授



---

## Notes

This repository is intended to serve as the permanent project repository for all materials related to this senior project, including source code, documents, slides, images, and future updates.
