import os
import uuid
import shutil
import re
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from ollama import chat, ChatResponse
from markdown_pdf import MarkdownPdf, Section

# --- FastAPI App Initialization ---
app = FastAPI(
    title="PDF Translation Service",
    description="Upload a PDF, translate its content, and receive a new PDF.",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Variables & Model Loading ---
# Load the Marker models once when the server starts to avoid reloading on each request.
# This significantly speeds up processing.

try:
    CONVERTER = PdfConverter(artifact_dict=create_model_dict())
except Exception as e:
    # If models fail to load, the server can't work.
    print(f"FATAL: Could not load Marker models. Error: {e}")
    CONVERTER = None

# --- Cleanup Function ---
def cleanup_temp_dir(temp_dir: str):
    """
    Removes the temporary directory and its contents.
    This function will be run in the background after the response is sent.
    """
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Successfully cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        print(f"Error during cleanup of {temp_dir}: {e}")


# --- API Endpoint for Translation ---
@app.post("/translate-pdf/")
async def translate_pdf_endpoint(
    background_tasks: BackgroundTasks,
    target_language: str = "Hindi", 
    file: UploadFile = File(...)
):
    """
    Accepts a PDF file and a target language, translates the text,
    and returns the translated PDF.
    """
    if not CONVERTER:
        raise HTTPException(status_code=500, detail="PDF processing models are not available.")

    # Create a unique temporary directory to store intermediate files
    temp_dir = f"temp_{uuid.uuid4()}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Add the cleanup task to be executed after the response is sent
    background_tasks.add_task(cleanup_temp_dir, temp_dir)
    
    original_pdf_path = os.path.join(temp_dir, file.filename)
    
    try:
        # 1. Save the uploaded PDF to a temporary file
        with open(original_pdf_path, "wb") as buffer:
            buffer.write(await file.read())

        # 2. Convert PDF to Markdown using Marker
        print("Starting PDF to Markdown conversion...")
        rendered = CONVERTER(original_pdf_path)
        text, _, images = text_from_rendered(rendered)
        print("Conversion successful.")

        # Save images if any are extracted
        for name, img in images.items():
            img_path = os.path.join(temp_dir, name)
            img.save(img_path, format="JPEG")

        # 3. Isolate image tags and replace with placeholders before translation
        image_tags = re.findall(r'!\[.*?\]\(.*?\)', text)
        text_for_translation = text
        for i, tag in enumerate(image_tags):
            placeholder = f"__IMAGE_PLACEHOLDER_{i}__"
            # Replace only the first occurrence to avoid issues with duplicate tags
            text_for_translation = text_for_translation.replace(tag, placeholder, 1)

        # 4. Translate the text using Ollama
        print(f"Translating text to {target_language}...")
        prompt = (
            f"Translate the following text to {target_language}. "
            "Only return the translated text itself. "
            "Do not include any explanations, greetings, or extra comments. "
            "Do not modify formatting or placeholders like __IMAGE_PLACEHOLDER_0__. "
            f"Text:\n\n{text_for_translation}"
        )
        
        response: ChatResponse = chat(
            model='gemma3n:e2b',
            messages=[{'role': 'user', 'content': prompt}]
        )
        translated_text_with_placeholders = response['message']['content']
        print("Translation successful.")

        # 5. Restore image tags with corrected, relative paths
        final_translated_text = translated_text_with_placeholders
        for i, original_tag in enumerate(image_tags):
            placeholder = f"__IMAGE_PLACEHOLDER_{i}__"
            # Extract the original filename from the tag, e.g., "figure-0-0.jpg"
            match = re.search(r'\((.*?)\)', original_tag)
            if match:
                original_filename = match.group(1)
                # Create a relative path that the PDF generator can resolve from the CWD.
                # Using forward slashes is more compatible for paths in markdown/html.
                relative_img_path = os.path.join(temp_dir, original_filename).replace(os.sep, '/')
                # Rebuild the tag with the new, correct relative path
                rebuilt_tag = original_tag.replace(original_filename, relative_img_path)
                # Replace the placeholder with the fully corrected image tag
                final_translated_text = final_translated_text.replace(placeholder, rebuilt_tag, 1)

        # 6. Convert the final translated Markdown back to a PDF
        pdf = MarkdownPdf()
        pdf.add_section(Section(final_translated_text, toc=False))
        
        translated_pdf_path = os.path.join(temp_dir, "output.pdf")
        pdf.save(translated_pdf_path)
        print(f"Translated PDF saved to: {translated_pdf_path}")

        # 7. Return the generated PDF
        return FileResponse(
            path=translated_pdf_path,
            media_type='application/pdf',
            filename=f"translated_{file.filename}"
        )

    except Exception as e:
        # Catch any errors during the process and return an informative message.
        print(f"An error occurred during processing: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
