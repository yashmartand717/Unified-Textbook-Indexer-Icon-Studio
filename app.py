import streamlit as st
import pdfplumber
import pandas as pd
from google import genai
from google.genai import types
import json
import io
import zipfile
import re
import time
import os
from dotenv import load_dotenv

# Load the hidden .env file
load_dotenv()

# --- 1. CONFIGURE YOUR AI CLIENT ---
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY)

def natural_sort_key(s):
    """Sorts strings with embedded numbers naturally (e.g., Chapter 2 before Chapter 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def extract_pdf_streams(uploaded_files):
    """Extracts all PDF file objects from direct uploads or unzips them from .zip archives."""
    pdf_streams = []
    
    for file in uploaded_files:
        filename = file.name.lower()
        
        # Handle ZIP files
        if filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(file) as zf:
                    valid_pdf_names = [
                        name for name in zf.namelist() 
                        if name.lower().endswith(".pdf") 
                        and not name.startswith("__MACOSX/") 
                        and not name.split("/")[-1].startswith("._")
                    ]
                    valid_pdf_names.sort(key=natural_sort_key)
                    
                    for name in valid_pdf_names:
                        pdf_bytes = io.BytesIO(zf.read(name))
                        pdf_bytes.name = name.split("/")[-1]
                        pdf_streams.append(pdf_bytes)
            except Exception as e:
                st.error(f"Error reading ZIP file {file.name}: {e}")
                
        # Handle standalone PDF files
        elif filename.endswith(".pdf"):
            pdf_streams.append(file)
            
    pdf_streams.sort(key=lambda x: natural_sort_key(x.name))
    return pdf_streams

def extract_text_from_pdf(pdf_file_obj):
    """Extracts all text from every page of a single PDF."""
    full_text = []
    with pdfplumber.open(pdf_file_obj) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text.append(f"--- PAGE {i+1} ---\n" + text)
    return "\n\n".join(full_text)

def process_text_with_ai(raw_text, filename, max_retries=3):
    """
    Passes chapter text AND filename to Gemini to extract structured data.
    """
    
    # We dynamically inject the filename into the prompt so the AI can't get the chapter number wrong.
    prompt = f"""
    You are an expert curriculum and textbook indexing system. I am providing you with the text of a school textbook chapter.
    
    Source File Name: {filename}
    
    Your task is to comprehensively extract the Chapter Number, Chapter Name, and ALL OF ITS SUBTOPICS.
    
    CRITICAL INSTRUCTIONS:
    1. Extract the exact Chapter Number and Chapter Title. 
       **CRUCIAL RULE:** Use the 'Source File Name' provided above as the ultimate source of truth for the Chapter Number (e.g., if the file is named 'ch15_something.pdf', the Chapter Number MUST be "15"). Do not let stray page numbers or typos in the text confuse you.
    2. Extract all main subtopics and section headings.
    3. If the book does not use numbers for subtopics, generate sequential subtopic IDs starting with the exact Chapter Number (e.g., 15.1, 15.2, 15.3).
    4. Ignore questions, exercises, 'Let's Check', 'Activities', 'Did You Know' sidebars, and generic page filler.
    
    Output STRICTLY a valid JSON array of objects.
    Format each item exactly like this:
    [
      {{
        "Chapter Number": "1",
        "Chapter Name": "Locating Places and Reading Maps",
        "Subtopic ID": "1.1",
        "Subtopic Name": "Shape of Earth"
      }}
    ]
    
    Textbook Content:
    {raw_text}
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=8192,
                ),
            )
            extracted_data = json.loads(response.text)
            return extracted_data
        except Exception as e:
            if attempt < max_retries:
                time.sleep(3 * attempt)
            else:
                st.error(f"Failed after {max_retries} attempts: {e}")
                return []

# --- 2. STREAMLIT UI ---
st.set_page_config(page_title="Universal Textbook Indexer", page_icon="📚", layout="wide")

st.title("📚 YASH'S Textbook Auto-Indexer")
st.markdown("Upload individual PDF chapters, multiple PDFs, or a **ZIP file**. The tool will automatically unpack, index, and stitch everything into a single Master Excel file.")

uploaded_files = st.file_uploader(
    "Upload PDF or ZIP files", 
    type=["pdf", "zip"], 
    accept_multiple_files=True
)

if uploaded_files:
    discovered_pdfs = extract_pdf_streams(uploaded_files)
    
    if discovered_pdfs:
        st.info(f"📁 Found **{len(discovered_pdfs)}** chapter PDF(s) ready for indexing:")
        with st.expander("View file processing order"):
            for idx, f in enumerate(discovered_pdfs, start=1):
                st.write(f"**{idx}.** `{f.name}`")
                
        if st.button("Extract All Chapters & Generate Master Excel", type="primary"):
            master_data = []
            progress_bar = st.progress(0, text="Starting extraction...")
            
            for idx, pdf_file in enumerate(discovered_pdfs):
                progress_percent = (idx + 1) / len(discovered_pdfs)
                progress_bar.progress(progress_percent, text=f"Processing chapter {idx+1} of {len(discovered_pdfs)}: `{pdf_file.name}`...")
                
                # Step 1: Read PDF
                raw_text = extract_text_from_pdf(pdf_file)
                
                if len(raw_text.strip()) < 50:
                    st.warning(f"`{pdf_file.name}` contains no selectable text (may require OCR). Skipping.")
                    continue
                
                # Step 2: Extract structured JSON via Gemini with auto-retry
                # Passing pdf_file.name to the AI function
                chapter_data = process_text_with_ai(raw_text, pdf_file.name)
                
                # Step 3: Format IDs as Excel text strings
                for item in chapter_data:
                    sub_id = item.get('Subtopic ID', '')
                    if not str(sub_id).startswith("'"):
                        item['Subtopic ID'] = f"'{sub_id}"
                        
                master_data.extend(chapter_data)
                
                # Small pause to maintain socket connection health
                time.sleep(1.5)
                
            progress_bar.empty()
            
            if not master_data:
                st.error("No structured data could be extracted from the uploaded files.")
            else:
                df = pd.DataFrame(master_data)
                
                # Export to in-memory Excel buffer
                # Export to in-memory Excel buffer
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Master Index')
                    
                    # --- NEW: AUTO-FIT COLUMN WIDTHS ---
                    worksheet = writer.sheets['Master Index']
                    from openpyxl.utils import get_column_letter
                    
                    for i, col in enumerate(df.columns):
                        # Find the longest string in the column (or the header), plus some padding
                        max_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 3
                        col_letter = get_column_letter(i + 1)
                        worksheet.column_dimensions[col_letter].width = max_len
                    # -----------------------------------
                
                st.success(f"🎉 Complete! Extracted {len(df['Chapter Number'].unique())} chapters with {len(df)} total rows.")
                st.dataframe(df, width="stretch")
                
                st.download_button(
                    label="📥 Download Master_Index.xlsx",
                    data=excel_buffer.getvalue(),
                    file_name="Master_Index.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("No valid PDF files found inside the uploaded file(s).")