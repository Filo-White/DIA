"""
Utility functions for DIA (Digital Intelligent Assistant)
Common helper functions and utilities
"""
import os
import re
import json
import markdown2
from bs4 import BeautifulSoup
from typing import Tuple, List, Dict, Any, Optional

from config import VALID_JOB_NUMBERS, STOP_COMMANDS, PHOTO_COMMANDS


def extract_json_from_markdown(text: str) -> str:
    """
    Extract JSON from markdown code blocks
    
    Args:
        text (str): Text potentially containing markdown JSON blocks
        
    Returns:
        str: Cleaned JSON string
    """
    # Remove markdown code blocks ```json ... ```
    if '```json' in text:
        # Extract content between ```json and ```
        start = text.find('```json') + 7  # Length of '```json'
        end = text.find('```', start)
        if end != -1:
            return text[start:end].strip()
    
    # Remove markdown code blocks ``` ... ```
    if '```' in text:
        # Extract content between first ``` and last ```
        start = text.find('```') + 3
        end = text.rfind('```')
        if end != -1 and end > start:
            return text[start:end].strip()
    
    # If no markdown blocks, return as is
    return text.strip()


def clean_markdown(text: str) -> Tuple[str, str]:
    """
    Clean markdown formatting and extract JSON values if present
    
    Args:
        text (str): Text potentially containing markdown and JSON
        
    Returns:
        tuple: (key, value) extracted from JSON
    """
    print(f"🔍 DEBUG - Testo ricevuto: {text[:200]}...")  # First 200 chars for debug
    
    # First, extract JSON from markdown blocks
    cleaned_text = extract_json_from_markdown(text)
    print(f"🔍 DEBUG - Testo dopo pulizia markdown: {cleaned_text}")
    
    try:
        # Try to parse as JSON directly
        json_obj = json.loads(cleaned_text)
        
        # Print key and value separately
        for chiave, valore in json_obj.items():
            print("Chiave:", chiave)
            print("Valore:", valore)
            return chiave, valore
            
    except json.JSONDecodeError as e:
        print(f"🔍 DEBUG - JSON parsing failed: {e}")
        try:
            # If direct JSON parsing fails, try cleaning with BeautifulSoup
            html = markdown2.markdown(cleaned_text)
            soup = BeautifulSoup(html, "html.parser")
            
            # Process ordered lists
            for ol in soup.find_all("ol"):  
                for i, li in enumerate(ol.find_all("li"), 1):
                    li.insert_before(f"{i}. ") 

            # Process unordered lists
            for ul in soup.find_all("ul"): 
                for li in ul.find_all("li"):
                    li.insert_before("- ") 
            
            # Convert <br> tags to newlines
            for br in soup.find_all("br"):
                br.replace_with("\n")
            
            # Get the cleaned text
            final_cleaned_text = soup.get_text(separator="\n", strip=True)
            print(f"🔍 DEBUG - Testo finale: {final_cleaned_text}")
            
            # Try to parse as JSON again
            json_obj = json.loads(final_cleaned_text)

            # Print key and value separately
            for chiave, valore in json_obj.items():
                print("Chiave:", chiave)
                print("Valore:", valore)
                return chiave, valore
                
        except (json.JSONDecodeError, Exception) as e:
            # If all parsing fails, return default values
            print(f"⚠️ Errore nel parsing della risposta JSON: {e}")
            print(f"⚠️ Testo originale: {text}")
            print(f"⚠️ Testo pulito: {cleaned_text}")
            return "altro", f"Risposta del sistema: {cleaned_text}"


def format_completion_message(key: str, value: str, job_number: str) -> Tuple[str, str]:
    """
    Format completion messages based on response key
    
    Args:
        key (str): Response key from JSON
        value (str): Response value from JSON
        job_number (str): Current job number
        
    Returns:
        tuple: (image_path, message) for completion display
    """
    if key == 'lavorofinito':
        image_path = f"content/foto_versioni/Job_{job_number}_completo.png"
        message = "Segui la dispozione in foto. Premi INVIO per continuare a fare domande"
        return image_path, message
    
    elif key == 'spedizione':
        image_path = f"content/foto_versioni/images{job_number}.png"
        message = "Ottimo lavoro! Usa questa etichetta. Premi invio per fare altre domande."
        return image_path, message
    
    elif key == 'inserireoggetto' or key == 'cercaoggetto':
        # FOTO CONTIENE BOX → Mostra immagine dell'oggetto da inserire
        # Check if it's a multiple objects request (separated by ||)
        if '||' in value:
            # Multiple objects - return list of tuples
            objects_data = []
            items = value.split('||')
            
            for item in items:
                split_val = item.split(";__")
                if len(split_val) > 1 and split_val[1] != "":
                    object_name = split_val[1].strip()
                    box_description = split_val[0].strip()
                    image_path = f"content/images/{object_name}/{object_name}_angle1.jpg"
                    backup_path = f"content/images/{object_name}/{object_name}.angle1.jpg"
                    
                    objects_data.append({
                        'description': box_description,
                        'object_name': object_name,
                        'image_path': image_path,
                        'backup_path': backup_path
                    })
            
            if objects_data:
                return ('multiple', objects_data)
        else:
            # Single object
            split_val = value.split(";__")
            if len(split_val) > 1 and split_val[1] != "":
                object_name = split_val[1]
                image_path = f"content/images/{object_name}/{object_name}_angle1.jpg"
                backup_path = f"content/images/{object_name}/{object_name}.angle1.jpg"
                message = "Questo è l'oggetto. Premi invio per fare altre domande."
                return image_path, message, backup_path
    
    elif key == 'usarescatola':
        # FOTO CONTIENE OGGETTI → NON mostrare immagine, solo risposta testuale
        # Non restituire nulla per evitare di mostrare immagini
        return None, None
    
    return None, None


def extract_response_value(value: str) -> str:
    """
    Extract the main response value, removing any metadata markers
    
    Args:
        value (str): Raw response value
        
    Returns:
        str: Cleaned response value
    """
    # Handle multiple objects (separated by ||)
    if '||' in value:
        items = value.split('||')
        cleaned_items = [item.split(";__")[0].strip() for item in items]
        return '\n'.join(cleaned_items)
    
    # Single object
    return value.split(";__")[0]


def print_welcome_message():
    """Print welcome message to console"""
    print("""
👋 Benvenuto nel DIA (Digital Intelligent Assistant)! 🛠️
🤖 Posso offrirti sia supporto vocale che testuale per l'assemblaggio.
📸 Per analizzare immagini, includi la parola 'FOTO' nella tua richiesta.
🚫 Per uscire, di' 'STOP' o 'FINE'.
🚀 Iniziamo!
    """)


def print_system_info():
    """Print system information"""
    print("\n" + "="*50)
    print("DIA - Digital Intelligent Assistant")
    print("Sistema multimodale per supporto assemblaggio")
    print("="*50 + "\n")


def validate_file_paths() -> Dict[str, bool]:
    """
    Validate that required file paths exist
    
    Returns:
        dict: Dictionary of file paths and their existence status
    """
    paths_to_check = {
        "content/pdf/": os.path.exists("content/pdf/"),
        "content/images/": os.path.exists("content/images/"),
        "content/foto_versioni/": os.path.exists("content/foto_versioni/"),
        "content/archivio/": os.path.exists("content/archivio/")
    }
    
    missing_paths = [path for path, exists in paths_to_check.items() if not exists]
    
    if missing_paths:
        print("⚠️ Percorsi mancanti:")
        for path in missing_paths:
            print(f"   - {path}")
        print("Alcuni file potrebbero non essere accessibili.")
    
    return paths_to_check


def create_default_directories():
    """Create default directories if they don't exist"""
    directories = [
        "content/archivio",
        "content/images", 
        "content/pdf",
        "content/foto_versioni"
    ]
    
    created = []
    for directory in directories:
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                created.append(directory)
            except OSError as e:
                print(f"❌ Errore nella creazione di {directory}: {e}")
    
    if created:
        print(f"✅ Cartelle create: {', '.join(created)}")


def safe_file_operation(operation, *args, **kwargs):
    """
    Safely execute file operations with error handling
    
    Args:
        operation: Function to execute
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        Result of operation or None if failed
    """
    try:
        return operation(*args, **kwargs)
    except Exception as e:
        print(f"❌ Errore nell'operazione file: {e}")
        return None


def format_time_duration(seconds: float) -> str:
    """
    Format time duration in a human-readable format
    
    Args:
        seconds (float): Time in seconds
        
    Returns:
        str: Formatted time string
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"


def log_error(error: Exception, context: str = ""):
    """
    Log error with context information
    
    Args:
        error (Exception): The exception that occurred
        context (str): Additional context information
    """
    error_msg = f"❌ Errore{' in ' + context if context else ''}: {str(error)}"
    print(error_msg)
    
    # Could be extended to write to log file
    # with open("error.log", "a") as f:
    #     f.write(f"{datetime.now()}: {error_msg}\n")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing/replacing invalid characters
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove multiple underscores
    filename = re.sub(r'_+', '_', filename)
    # Remove leading/trailing underscores and whitespace
    filename = filename.strip('_ ')
    
    return filename if filename else "unnamed_file"


def get_system_status() -> Dict[str, Any]:
    """
    Get current system status information
    
    Returns:
        dict: System status information
    """
    return {
        "directories_exist": validate_file_paths(),
        "current_working_directory": os.getcwd(),
        "python_executable": os.sys.executable,
        "environment_variables": {
            "OPENAI_API_KEY": "SET" if os.getenv('OPENAI_API_KEY') else "NOT SET"
        }
    }


def extract_json_from_markdown(text: str) -> str:
    """
    Extract JSON data from markdown text
    
    Args:
        text (str): Markdown text containing JSON data
        
    Returns:
        str: Extracted JSON data
    """
    # Implement JSON extraction logic here
    pass


# Export commonly used functions
__all__ = [
    'validate_inputs',
    'is_stop_command', 
    'is_photo_command',
    'clean_markdown',
    'format_completion_message',
    'extract_response_value',
    'print_welcome_message',
    'print_system_info',
    'validate_file_paths',
    'create_default_directories',
    'safe_file_operation',
    'format_time_duration',
    'log_error',
    'sanitize_filename',
    'get_system_status'
]
