import pdfplumber
import pandas as pd
import re
import os

def extract_book_data(pdf_path):
    extracted_data = []
    
    # Upgraded Regex: 
    # Group 1 captures the Chapter Num (e.g., '1')
    # Group 2 captures the Subtopic Num (e.g., '2')
    # Group 3 captures the Name (e.g., 'Patterns in Numbers')
    subtopic_pattern = re.compile(r'^(\d+)\.(\d+)\s+(.+)$')
    
    current_chapter_num = None
    current_chapter_name = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            
            # --- STEP 1: Find the Chapter Title using Font Size ---
            # Extract all words on the page along with their font sizes
            words = page.extract_words(extra_attrs=['size'])
            page_largest_text = "Unknown Title"
            
            if words:
                # Find the maximum font size used on this specific page
                max_size = max(word['size'] for word in words)
                
                # Group all words that share this maximum font size
                title_words = [word['text'] for word in words if word['size'] >= max_size - 1]
                
                # Combine them into a single string (e.g., "1 PATTERNS IN MATHEMATICS")
                page_largest_text = " ".join(title_words)
            
            # --- STEP 2: Extract Subtopics and Assign Chapter Info ---
            text = page.extract_text()
            if text:
                for line in text.split('\n'):
                    line = line.strip()
                    
                    # Check if the line matches the "X.Y Subtopic" format
                    match = subtopic_pattern.match(line)
                    if match:
                        ch_num = match.group(1)   
                        sub_num = match.group(2)  
                        sub_name = match.group(3) 
                        
                        # If we detect a NEW chapter number, update our trackers
                        if current_chapter_num != ch_num:
                            current_chapter_num = ch_num
                            
                            # Because this is the start of a new chapter, the largest 
                            # text we found on this page is almost certainly the Chapter Title.
                            # We clean out any numbers from the title string just in case.
                            clean_title = re.sub(r'^\d+\s*', '', page_largest_text)
                            current_chapter_name = clean_title 
                            
                        extracted_data.append({
                            "Chapter Number": current_chapter_num,
                            "Chapter Name": current_chapter_name,
                            "Subtopic ID": f"{ch_num}.{sub_num}",
                            "Subtopic Name": sub_name
                        })
                        
    return extracted_data

# Run the automated extraction
pdf_file = "ch1_patters in mathematics.pdf" # Replace with ANY book or chapter PDF
print(f"Scanning {pdf_file}...")

data = extract_book_data(pdf_file)

# Save to Excel
df = pd.DataFrame(data)
df.to_excel("Fully_Automated_Index.xlsx", index=False)
print("Extraction Complete! Check Fully_Automated_Index.xlsx")