"""
Configuration file for DIA (Digital Intelligent Assistant)
Contains all system configurations and constants
"""
import os
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# SYSTEM CONFIGURATION
# =============================================================================

# Hardware Configuration
MIC_INDEX = 1  # Microphone index - MODIFY FOR YOUR SETUP
CAMERA_INDEX = 0  # Camera index - MODIFY FOR YOUR SETUP

# File Paths
IMAGE_PATH = "captured_image.jpg"
EXCEL_FILENAME = "DIA_METRICS/DIA_metrics.xlsx"

# Audio Configuration
SILENCE_THRESHOLD = 1500  # Silence threshold in RMS
SILENCE_DURATION = 3.5  # Duration in seconds for silence detection
API_URL = "https://api.openai.com/v1/audio/transcriptions"

# OpenAI Configuration
# API key loaded from .env file
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Speech Configuration
SPEECH_RATE = 180  # Speech rate for TTS (higher = faster)

# =============================================================================
# CONTENT CONFIGURATION
# =============================================================================

# PDF Paths for knowledge base
PDF_PATHS = [
    "content/pdf/item_details.pdf",
    "content/pdf/manuale_assemblaggio_XX1.pdf",
    "content/pdf/manuale_assemblaggio_XX2.pdf"
]

# =============================================================================
# AUDIO MESSAGES
# =============================================================================

AUDIO_MESSAGES = {
    'welcome': """Benvenuto! Sono un assistente in grado di aiutarti in questo processo di assemblaggio.
Posso offrirti sia supporto vocale che testuale. Fammi una domanda e ti risponderò in base alle informazioni di cui dispongo.
Se hai bisogno di aiuto con un'immagine, basta che la tua richiesta contenga la parola 'FOTO'. Scatta una foto secondo le istruzioni che ti sono state date e io la analizzerò per te. 
Per uscire, ti basta dire 'STOP' o 'FINE'.
Iniziamo!""",
    
    'request_input': "Inserisci la tua richiesta: ",
    'photo_request': "Bene, posiziona l'oggetto di cui vuoi che scatti la foto. Mostrami anche le mani con il dorso rivolto verso l'alto.",
    'photo_accepted': "Bene, chiedimi quello che vuoi sulla foto.",
    'goodbye': "Spero di esserti stato utile! Arrivederci!",
    'photo_confirm': "La foto va bene? Dì 'si' per confermare o 'no' per scattare di nuovo.",
    'camera_opening': "Adesso aprirò la fotocamera per scattare una foto.",
    'photo_instructions': "Posiziona l'oggetto e premi SPAZIO per scattare la foto",
    'photo_taken': "Foto scattata! Premi INVIO per confermare o SPAZIO per riprovare",
    'photo_retake': "Scatto una nuova foto",
    'photo_confirmed': "Foto confermata! Salvataggio in corso...",
    'photo_saved': "Immagine salvata con successo!",
    'camera_error': "ERRORE: non è stato possibile catturare l'immagine",
    'photo_accept': "Foto accettata."
}

# =============================================================================
# EXCEL METRICS COLUMNS
# =============================================================================

EXCEL_COLUMNS = [
    "Participant", 
    "Job", 
    "Request", 
    "DIA Answer", 
    "Interaction Code",
    "Time between call and end of request (sec)",
    "Time between end of request and start of response (sec)",
    "Time between start and end of response (sec)",
    "Image captured?", 
    "Image shown?",
    "tempo foto scattata", 
    "tempo foto scattata",
    "tempo scelta foto", 
    "tempo scelta foto"
]

# =============================================================================
# JOB CONFIGURATION
# =============================================================================

VALID_JOB_NUMBERS = ["1", "2"]

# =============================================================================
# COMMAND PATTERNS
# =============================================================================

STOP_COMMANDS = ["stop", "fine", "fermati", "esci"]
PHOTO_COMMANDS = ["foto", "immagine", "scattare"]
PHOTO_CAPTURE_COMMANDS = ["foto", "scatta", "scatta la foto"]

# =============================================================================
# VECTOR STORE CONFIGURATION
# =============================================================================

CHROMA_COLLECTION_NAME = "calendario_unicorni"

# =============================================================================
# MODEL CONFIGURATION
# =============================================================================

LLM_MODEL = "gpt-4o"
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 1024
LLM_USE_JSON_MODE = True  # Force JSON output from LLM (recommended)

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_job_number(job_number: str) -> bool:
    """Validate if job number is valid"""
    return job_number in VALID_JOB_NUMBERS

def get_openai_api_key() -> str:
    """Get OpenAI API key with validation"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")
    return api_key
