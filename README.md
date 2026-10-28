# Unified Textbook Indexer & Icon Studio

A Streamlit app that turns textbook PDFs into a structured topic index and generates a matching icon for each topic.

## How it works
1. Upload a textbook PDF.
2. Text is extracted with `pdfplumber` and structured into an index using OpenAI.
3. Icons are generated for each topic and uploaded to Google Cloud Storage.
4. Download the results as spreadsheets or a ZIP.

## Tech stack
Python · Streamlit · OpenAI API · pdfplumber · pandas · Google Cloud Storage

## Setup
```bash
pip install -r requirements.txt
```
Create a `.env` file (or Streamlit secrets) with:
```
OPENAI_API_KEY=...
GCP_PROJECT_ID=...
GCS_BUCKET_NAME=...
```
Then run:
```bash
streamlit run app.py
```
