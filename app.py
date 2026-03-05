"""
Flask Web Interface for DIA (Digital Intelligent Assistant)
Modern web interface with chat and camera integration
"""
# CRITICAL: Import init_env FIRST to patch ChromaDB before it loads
import init_env

import io
import os
import cv2
import base64
import time
import logging
from flask import Flask, render_template, request, jsonify, session, Response, send_file
import uuid
from datetime import datetime
from PIL import Image

# Import DIA services
from rag_service import RAGService, clean_markdown
from metrics_service import MetricsService, TimeTracker
from utils import format_completion_message, extract_response_value

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dia-secret-key-change-in-production'

# Global services
rag_service = None
metrics_service = None
active_sessions = {}

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebDIASession:
    """Manages a DIA session for web interface"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.participant_number = ""
        self.job_number = ""
        self.excel_filename = ""  # File Excel specifico per questa sessione
        self.rag_service = RAGService()
        self.metrics_service = None  # Sarà inizializzato in initialize_session
        self.conversation_history = []
        self.camera_active = False
        self.current_image = None
        self.time_tracker = TimeTracker()  # Per tracking metriche temporali
        
        # 🧠 Sistema di memoria conversazionale
        self.conversation_memory = {
            'objects_discussed': {},  # {nome_oggetto: [lista di interazioni]}
            'boxes_discussed': {},    # {numero_box: [lista di interazioni]}
            'last_topic': None,       # Ultimo argomento discusso
            'context_summary': []     # Riassunto delle ultime N interazioni
        }
        
    def initialize_session(self, participant_number: str, job_number: str):
        """Initialize session with participant info"""
        self.participant_number = participant_number
        self.job_number = job_number
        
        # Crea cartella DIA_METRICS se non esiste
        metrics_dir = "DIA_METRICS"
        os.makedirs(metrics_dir, exist_ok=True)
        
        # Crea file Excel con timestamp per questa sessione nella cartella DIA_METRICS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.excel_filename = os.path.join(metrics_dir, f"DIA_metrics_{timestamp}.xlsx")
        logger.info(f"📊 Creating session Excel file: {self.excel_filename}")
        
        # Inizializza MetricsService con il file specifico della sessione
        self.metrics_service = MetricsService(excel_filename=self.excel_filename)
        self.metrics_service.setup_session(participant_number, job_number)
        self.rag_service.create_rag_chain(job_number)
        
        # Add welcome message
        self.conversation_history.append({
            'type': 'system',
            'message': f'Sessione inizializzata per Partecipante {participant_number}, Job {job_number}',
            'timestamp': datetime.now().isoformat()
        })
    
    def process_message(self, message: str, image_data: str = None, 
                       voice_recording_start: float = None, voice_recording_end: float = None) -> dict:
        """Process user message and return response"""
        try:
            # ⏱️ TIMING 1: Start call (inizio registrazione vocale o arrivo richiesta)
            if voice_recording_start:
                # Use voice recording start time
                self.time_tracker.start_time = voice_recording_start
                logger.info(f"🎤 Voice recording started at: {voice_recording_start}")
            else:
                # Fallback to current time for text input
                self.time_tracker.start_call()
            
            logger.info(f"🔍 Processing message: {message}")
            logger.info(f"🔍 Has image: {image_data is not None}")
            
            # Add user message to history
            user_msg = {
                'type': 'user',
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'has_image': image_data is not None
            }
            self.conversation_history.append(user_msg)
            
            # Handle image if provided
            if image_data:
                logger.info("🔍 Saving captured image...")
                self._save_captured_image(image_data)
                # Default query for image analysis if not specified
                if not message or message.lower() in ['foto', 'immagine', 'analizza', 'analizza immagine', 'analizza questa immagine']:
                    message = """Analizza attentamente l'immagine catturata e identifica TUTTI gli elementi presenti:

1. Se ci sono OGGETTI: identifica OGNI oggetto presente (usando il mapping degli oggetti disponibili) e indica per CIASCUNO in quale box deve essere inserito. Se ci sono più oggetti, elencali tutti separati da '||'.

2. Se ci sono BOX: leggi il numero su OGNI box presente e indica per CIASCUNA quale oggetto deve essere inserito. Se ci sono più box, elencale tutte separate da '||'.

3. Se ci sono sia OGGETTI che BOX: analizza entrambi separatamente.

IMPORTANTE: Non limitarti al primo elemento che vedi, ma analizza l'intera immagine per identificare TUTTI gli oggetti o box presenti. Rispondi in modo chiaro per ogni elemento riconosciuto."""
                    logger.info(f"🔍 Using default image analysis query for multiple objects")
            
            # ⏱️ TIMING 2: End request (fine registrazione vocale o elaborazione input)
            if voice_recording_end:
                # Use voice recording end time
                self.time_tracker.end_request_time = voice_recording_end
                logger.info(f"🎤 Voice recording ended at: {voice_recording_end}")
                recording_duration = voice_recording_end - voice_recording_start
                logger.info(f"⏱️ Voice recording duration: {recording_duration:.2f}s")
            else:
                # Fallback to current time
                self.time_tracker.end_request()
            
            # Process with RAG (no timing for G and H here - will be updated by audio playback)
            logger.info("🔍 Invoking RAG chain...")
            
            # 🧠 Ottieni contesto dalla memoria
            memory_context = self._get_memory_context()
            
            # Passa il messaggio con il contesto della memoria al RAG
            response = self.rag_service.invoke_chain(message, memory_context)
            logger.info(f"🔍 RAG response received: {response[:100]}...")
            
            # Clean and extract response
            logger.info("🔍 Cleaning markdown response...")
            chiave, valore = clean_markdown(response)
            logger.info(f"🔍 Extracted key: {chiave}, value: {valore[:100]}...")
            
            cleaned_response = extract_response_value(valore)
            logger.info(f"🔍 Cleaned response: {cleaned_response[:100]}...")
            
            # Handle special responses (detect if image shown)
            special_content = self._handle_special_responses(chiave, valore)
            image_shown = "Yes" if special_content else "No"
            
            # Create response object
            dia_response = {
                'type': 'assistant',
                'message': cleaned_response,
                'raw_response': response,
                'response_type': chiave,
                'timestamp': datetime.now().isoformat(),
                'special_content': special_content
            }
            
            self.conversation_history.append(dia_response)
            
            # 🧠 Aggiorna la memoria conversazionale
            self._update_conversation_memory(message, valore, chiave)
            
            # Calculate Time F (voice recording duration or processing time)
            if voice_recording_start and voice_recording_end:
                # Voice input: Time F = duration of voice recording
                time_for_request = voice_recording_end - voice_recording_start
                logger.info(f"⏱️ Time F (voice recording): {time_for_request:.2f}s")
            else:
                # Text input: Time F = processing time (very small)
                time_for_request = self.time_tracker.end_request_time - self.time_tracker.start_time
                logger.info(f"⏱️ Time F (text processing): {time_for_request:.2f}s")
            
            # Time G and H will be updated later when audio playback finishes
            # For now, save as 0 (placeholder for voice) or small values (for text)
            time_for_dia = 0.0  # Will be updated by update_audio_timing
            time_for_response = 0.0  # Will be updated by update_audio_timing
            
            logger.info(f"⏱️ Initial metrics saved: Time F={time_for_request:.2f}s (Time G and H will be updated after audio)")
            
            # Log interaction with Time F only
            self.metrics_service.log_interaction(
                request=message,
                response=cleaned_response,  # ✅ Salva risposta pulita, non JSON
                time_for_request=time_for_request,
                time_for_dia=time_for_dia,  # Placeholder, will be updated
                time_for_response=time_for_response,  # Placeholder, will be updated
                image_captured="Yes" if image_data else "No",
                image_shown=image_shown
            )
            
            # Archive captured image
            if image_data:
                self.metrics_service.move_captured_image("captured_image.jpg", "content/archivio")
            
            logger.info("🔍 Message processed successfully")
            return dia_response
            
        except Exception as e:
            error_msg = f'Errore nel processamento: {str(e)}'
            error_response = {
                'type': 'error',
                'message': error_msg,
                'timestamp': datetime.now().isoformat()
            }
            self.conversation_history.append(error_response)
            logger.error(f"❌ Error processing message: {e}", exc_info=True)
            return error_response
    
    def _save_captured_image(self, image_data: str):
        """Save base64 image data to file"""
        try:
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            # Decode and save
            image_bytes = base64.b64decode(image_data)
            with open('captured_image.jpg', 'wb') as f:
                f.write(image_bytes)
                
            self.current_image = 'captured_image.jpg'
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
    
    def _update_conversation_memory(self, message: str, response: str, response_key: str):
        """Aggiorna la memoria conversazionale con nuove informazioni"""
        import re
        from datetime import datetime
        
        timestamp = datetime.now().isoformat()
        
        # Estrai numeri di box dalla conversazione (es: "box 5", "scatola 12")
        box_pattern = r'\b(?:box|scatola)\s*(\d+)\b'
        box_matches = re.findall(box_pattern, message.lower(), re.IGNORECASE)
        
        for box_num in box_matches:
            if box_num not in self.conversation_memory['boxes_discussed']:
                self.conversation_memory['boxes_discussed'][box_num] = []
            
            self.conversation_memory['boxes_discussed'][box_num].append({
                'timestamp': timestamp,
                'question': message,
                'response': response,
                'response_type': response_key
            })
        
        # Estrai nomi di oggetti dalla risposta (dopo il separatore ;__)
        if ';__' in response:
            # Gestisci risposte multiple separate da ||
            if '||' in response:
                parts = response.split('||')
                for part in parts:
                    if ';__' in part:
                        object_name = part.split(';__')[1].strip()
                        self._add_object_to_memory(object_name, message, response, response_key, timestamp)
            else:
                object_name = response.split(';__')[1].strip()
                self._add_object_to_memory(object_name, message, response, response_key, timestamp)
        
        # Aggiorna ultimo argomento
        if response_key == 'inserireoggetto':
            self.conversation_memory['last_topic'] = 'inserimento_oggetto'
        elif response_key == 'usarescatola':
            self.conversation_memory['last_topic'] = 'scelta_scatola'
        elif response_key == 'lavorofinito':
            self.conversation_memory['last_topic'] = 'completamento'
        else:
            self.conversation_memory['last_topic'] = 'altro'
        
        # Mantieni solo le ultime 5 interazioni nel contesto
        context_entry = {
            'timestamp': timestamp,
            'question': message[:100],  # Limita lunghezza
            'response_type': response_key,
            'response_summary': response[:150]  # Limita lunghezza
        }
        
        self.conversation_memory['context_summary'].append(context_entry)
        if len(self.conversation_memory['context_summary']) > 5:
            self.conversation_memory['context_summary'].pop(0)
    
    def _add_object_to_memory(self, object_name: str, message: str, response: str, response_key: str, timestamp: str):
        """Aggiunge un oggetto alla memoria"""
        if object_name not in self.conversation_memory['objects_discussed']:
            self.conversation_memory['objects_discussed'][object_name] = []
        
        self.conversation_memory['objects_discussed'][object_name].append({
            'timestamp': timestamp,
            'question': message,
            'response': response,
            'response_type': response_key
        })
    
    def _get_memory_context(self) -> str:
        """Genera un contesto dalla memoria per il prompt"""
        memory_context = []
        
        # Aggiungi informazioni sugli oggetti già discussi
        if self.conversation_memory['objects_discussed']:
            memory_context.append("\n=== OGGETTI GIÀ DISCUSSI ===")
            for obj_name, interactions in self.conversation_memory['objects_discussed'].items():
                last_interaction = interactions[-1]
                memory_context.append(
                    f"- {obj_name}: discusso {len(interactions)} volta/e. "
                    f"Ultima volta: {last_interaction['response'][:100]}..."
                )
        
        # Aggiungi informazioni sulle box già discusse
        if self.conversation_memory['boxes_discussed']:
            memory_context.append("\n=== BOX GIÀ DISCUSSE ===")
            for box_num, interactions in self.conversation_memory['boxes_discussed'].items():
                last_interaction = interactions[-1]
                memory_context.append(
                    f"- Box {box_num}: discussa {len(interactions)} volta/e. "
                    f"Ultima volta: {last_interaction['response'][:100]}..."
                )
        
        # Aggiungi contesto recente
        if self.conversation_memory['context_summary']:
            memory_context.append("\n=== CONTESTO RECENTE ===")
            for i, ctx in enumerate(self.conversation_memory['context_summary'][-3:], 1):
                memory_context.append(
                    f"{i}. [{ctx['response_type']}] {ctx['question']} -> {ctx['response_summary']}"
                )
        
        # Aggiungi ultimo argomento
        if self.conversation_memory['last_topic']:
            memory_context.append(f"\n=== ULTIMO ARGOMENTO: {self.conversation_memory['last_topic']} ===")
        
        return "\n".join(memory_context) if memory_context else ""
    
    def _handle_special_responses(self, key: str, value: str) -> dict:
        """Handle special response types that require additional content"""
        completion_result = format_completion_message(key, value, self.job_number)
        
        # Handle multiple objects
        if completion_result and isinstance(completion_result, tuple) and completion_result[0] == 'multiple':
            objects_data = completion_result[1]
            multiple_images = []
            
            for obj_data in objects_data:
                image_path = obj_data['image_path']
                backup_path = obj_data['backup_path']
                description = obj_data['description']
                object_name = obj_data['object_name']
                
                # Try primary path
                if os.path.exists(image_path):
                    try:
                        with open(image_path, 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                        
                        multiple_images.append({
                            'image_data': img_data,
                            'description': description,
                            'object_name': object_name
                        })
                        continue
                    except Exception as e:
                        logger.error(f"Error loading image from {image_path}: {e}")
                
                # Try backup path
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                        
                        multiple_images.append({
                            'image_data': img_data,
                            'description': description,
                            'object_name': object_name
                        })
                    except Exception as e:
                        logger.error(f"Error loading backup image from {backup_path}: {e}")
            
            if multiple_images:
                return {
                    'type': 'multiple_objects',
                    'images': multiple_images,
                    'response_key': key
                }
        
        # Handle single object/image
        if completion_result and len(completion_result) >= 2:
            image_path = completion_result[0]
            message = completion_result[1]
            backup_path = completion_result[2] if len(completion_result) > 2 else None
            
            # Try primary image path
            if image_path and os.path.exists(image_path):
                try:
                    with open(image_path, 'rb') as img_file:
                        img_data = base64.b64encode(img_file.read()).decode()
                    
                    # Determine image type based on key
                    image_type = 'object_image' if key == 'inserireoggetto' else 'completion_image'
                    
                    return {
                        'type': image_type,
                        'image_data': img_data,
                        'message': message,
                        'image_path': image_path,
                        'response_key': key
                    }
                except Exception as e:
                    logger.error(f"Error loading image from {image_path}: {e}")
            
            # Try backup path if primary fails
            if backup_path and os.path.exists(backup_path):
                try:
                    with open(backup_path, 'rb') as img_file:
                        img_data = base64.b64encode(img_file.read()).decode()
                    
                    image_type = 'object_image' if key == 'inserireoggetto' else 'completion_image'
                    
                    return {
                        'type': image_type,
                        'image_data': img_data,
                        'message': message,
                        'image_path': backup_path,
                        'response_key': key
                    }
                except Exception as e:
                    logger.error(f"Error loading backup image from {backup_path}: {e}")
        
        return None


@app.route('/')
def index():
    """Main interface page"""
    return render_template('index.html')


@app.route('/api/start_session', methods=['POST'])
def start_session():
    """Initialize a new DIA session"""
    try:
        data = request.json
        participant_number = data.get('participant_number', '').strip()
        job_number = data.get('job_number', '').strip()
        
        if not participant_number or job_number not in ['1', '2']:
            return jsonify({
                'success': False,
                'error': 'Parametri di sessione non validi'
            }), 400
        
        # Create new session
        session_id = str(uuid.uuid4())
        web_session = WebDIASession(session_id)
        web_session.initialize_session(participant_number, job_number)
        
        # Store in active sessions
        active_sessions[session_id] = web_session
        
        # Store in Flask session
        session['dia_session_id'] = session_id
        
        logger.info(f"✅ Session started: {session_id}, Excel file: {web_session.excel_filename}")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': f'Sessione inizializzata per Partecipante {participant_number}, Job {job_number}',
            'excel_filename': web_session.excel_filename
        })
        
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Process user message"""
    try:
        data = request.json
        session_id = session.get('dia_session_id')
        
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Sessione non trovata'
            }), 404
        
        web_session = active_sessions[session_id]
        message = data.get('message', '').strip()
        image_data = data.get('image_data')
        
        # ⏱️ Extract voice timing if provided
        voice_recording_start = data.get('voice_recording_start')
        voice_recording_end = data.get('voice_recording_end')
        
        if voice_recording_start and voice_recording_end:
            logger.info(f"🎤 Received voice timing: start={voice_recording_start}, end={voice_recording_end}, duration={voice_recording_end - voice_recording_start:.2f}s")
        
        if not message and not image_data:
            return jsonify({
                'success': False,
                'error': 'Messaggio o immagine richiesti'
            }), 400
        
        # Process the message with voice timing
        response = web_session.process_message(
            message, 
            image_data,
            voice_recording_start,
            voice_recording_end
        )
        
        return jsonify({
            'success': True,
            'response': response
        })
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/get_history')
def get_history():
    """Get conversation history"""
    try:
        session_id = session.get('dia_session_id')
        
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Sessione non trovata'
            }), 404
        
        web_session = active_sessions[session_id]
        
        return jsonify({
            'success': True,
            'history': web_session.conversation_history
        })
        
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/update_audio_timing', methods=['POST'])
def update_audio_timing():
    """Update timing metrics for audio playback"""
    try:
        session_id = session.get('dia_session_id')
        
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Sessione non trovata'
            }), 404
        
        web_session = active_sessions[session_id]
        data = request.json
        
        voice_recording_end = data.get('voice_recording_end')
        audio_response_start = data.get('audio_response_start')
        audio_response_end = data.get('audio_response_end')
        
        # We need at least audio start and end times
        if not audio_response_start or not audio_response_end:
            return jsonify({
                'success': False,
                'error': 'Missing audio timing data'
            }), 400
        
        # Calculate Time H (audio playback duration) - always present
        time_h = audio_response_end - audio_response_start
        
        # Calculate Time G (latency until audio starts)
        if voice_recording_end:
            # Voice input: Time G = time from end of voice recording to start of audio
            time_g = audio_response_start - voice_recording_end
            logger.info(f"⏱️ Updating audio timing (VOICE): Time G={time_g:.2f}s, Time H={time_h:.2f}s")
        else:
            # Text input: Time G = time from message processing to audio start
            # We'll keep the existing Time G (which was calculated from backend processing)
            # and only update Time H
            time_g = None  # Don't update Time G for text input
            logger.info(f"⏱️ Updating audio timing (TEXT): Time H={time_h:.2f}s (Time G unchanged)")
        
        # Update the last interaction in Excel
        web_session.metrics_service.update_last_interaction_timing(time_g, time_h)
        
        response_data = {
            'success': True,
            'message': 'Audio timing updated',
            'time_h': round(time_h, 2)
        }
        
        if time_g is not None:
            response_data['time_g'] = round(time_g, 2)
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error updating audio timing: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/get_memory', methods=['GET'])
def get_memory():
    """Get conversation memory state"""
    try:
        session_id = session.get('dia_session_id')
        
        if not session_id or session_id not in active_sessions:
            return jsonify({
                'success': False,
                'error': 'Sessione non trovata'
            }), 404
        
        web_session = active_sessions[session_id]
        
        return jsonify({
            'success': True,
            'memory': {
                'objects_discussed': {
                    obj: len(interactions) 
                    for obj, interactions in web_session.conversation_memory['objects_discussed'].items()
                },
                'boxes_discussed': {
                    box: len(interactions) 
                    for box, interactions in web_session.conversation_memory['boxes_discussed'].items()
                },
                'last_topic': web_session.conversation_memory['last_topic'],
                'context_count': len(web_session.conversation_memory['context_summary'])
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting memory: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/end_session', methods=['POST'])
def end_session():
    """End current session"""
    try:
        session_id = session.get('dia_session_id')
        
        if session_id and session_id in active_sessions:
            # Get session stats and Excel filename
            web_session = active_sessions[session_id]
            stats = web_session.metrics_service.get_session_stats()
            excel_filename = web_session.excel_filename
            
            logger.info(f"📊 Session ended. Excel file: {excel_filename}")
            
            # Store Excel filename in Flask session for download
            session['excel_filename'] = excel_filename
            
            # Remove from active sessions
            del active_sessions[session_id]
            session.pop('dia_session_id', None)
            
            return jsonify({
                'success': True,
                'message': 'Sessione terminata',
                'stats': stats,
                'excel_filename': excel_filename
            })
        
        return jsonify({
            'success': True,
            'message': 'Nessuna sessione attiva'
        })
        
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/text_to_speech', methods=['POST'])
def text_to_speech():
    """Convert text to speech using OpenAI TTS API"""
    try:
        from openai import OpenAI
        from config import get_openai_api_key
        
        data = request.json
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                'success': False,
                'error': 'Testo richiesto'
            }), 400
        
        # Limit text length for TTS (max 4096 chars for OpenAI)
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        # Initialize OpenAI client
        client = OpenAI(api_key=get_openai_api_key())
        
        # Ensure text is in Italian by prepending language hint
        # This helps the TTS model maintain Italian pronunciation
        italian_text = text
        
        # Generate speech using OpenAI TTS
        # Using 'nova' voice - warm and expressive, works well with Italian
        # Options: alloy, echo, fable, onyx, nova, shimmer
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",  # High quality model
            voice="nova",  # Nova voice - natural Italian pronunciation
            input=italian_text,
            speed=0.95,  # Slightly slower for better Italian clarity
            instructions=(
        "Parla esclusivamente in italiano standard (it-IT). "
        "NON DEVI MAI E POI MAI USARE UN ACCENTO DIVERSO DA QUELLO ITALIANO."
        "QUALSIASI PAROLA DEVE ESSERE PRONUNCIATA IN ITALIANO"
    ),
        )
        
        # Return audio as response
        return Response(
            response.content,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'inline; filename="speech.mp3"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error in TTS: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/download_metrics', methods=['GET'])
def download_metrics():
    """Download the DIA metrics Excel file for current session"""
    try:
        session_id = session.get('dia_session_id')
        excel_filename = None
        
        # Try to get Excel filename from active session first
        if session_id and session_id in active_sessions:
            web_session = active_sessions[session_id]
            excel_filename = web_session.excel_filename
            logger.info(f"📥 Getting Excel filename from active session: {excel_filename}")
        
        # If not in active sessions, try to get from Flask session (after end_session)
        if not excel_filename:
            excel_filename = session.get('excel_filename')
            if excel_filename:
                logger.info(f"📥 Getting Excel filename from Flask session: {excel_filename}")
                # Clear it after use
                session.pop('excel_filename', None)
        
        # Fallback to default if still not found
        if not excel_filename:
            from config import EXCEL_FILENAME
            excel_filename = EXCEL_FILENAME
            logger.warning(f"⚠️ Using fallback Excel filename: {excel_filename}")
        
        # Check if file exists
        if not os.path.exists(excel_filename):
            logger.error(f"❌ Metrics file not found: {excel_filename}")
            return jsonify({
                'success': False,
                'error': 'File metriche non trovato'
            }), 404
        
        logger.info(f"✅ Downloading metrics file: {excel_filename}")
        
        # Send file for download with original filename
        return send_file(
            excel_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=os.path.basename(excel_filename)
        )
        
    except Exception as e:
        logger.error(f"Error downloading metrics: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500




if __name__ == '__main__':
    # Ensure required directories exist
    os.makedirs('content/archivio', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('DIA_METRICS', exist_ok=True)
    
    # Run the Flask app
    logger.info("Starting DIA Web Interface...")
    print("\n" + "="*50)
    print("🌐 DIA Web Interface - SERVER AVVIATO")
    print("="*50)
    print("📍 Apri il browser all'indirizzo:")
    print("   http://localhost:5000")
    print("   oppure http://127.0.0.1:5000")
    print("="*50)
    print("🛑 Premi Ctrl+C per fermare il server")
    print("="*50 + "\n")
    
    # Use 0.0.0.0 to allow access from outside the container
    app.run(debug=False, host='0.0.0.0', port=5000)
