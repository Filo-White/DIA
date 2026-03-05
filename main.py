"""
Main application for DIA (Digital Intelligent Assistant)
Orchestrates all services and handles the main conversation loop
"""
import os
import cv2
import time
import nest_asyncio
from typing import Optional

# Import LangGraph components
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.messages import HumanMessage

# Import local services
from config import MIC_INDEX, CAMERA_INDEX, AUDIO_MESSAGES, get_openai_api_key
from audio_service import AudioService
from vision_service import VisionService
from rag_service import RAGService, clean_markdown
from metrics_service import MetricsService, TimeTracker
from utils import (
    validate_inputs, is_stop_command, is_photo_command,
    format_completion_message, extract_response_value,
    print_welcome_message, print_system_info, create_default_directories
)


class DIASystem:
    """Main DIA System orchestrator"""
    
    def __init__(self):
        # Initialize services
        self.audio_service = AudioService(MIC_INDEX)
        self.vision_service = VisionService(CAMERA_INDEX)
        self.rag_service = RAGService()
        self.metrics_service = MetricsService()
        self.time_tracker = TimeTracker()
        
        # Session variables
        self.participant_number = ""
        self.job_number = ""
        self.cap = None
        
        # LangGraph components
        self.workflow = None
        self.app = None
        
        # Initialize system
        self._setup_system()
    
    def _setup_system(self):
        """Setup system components"""
        # Apply nest_asyncio for Jupyter compatibility
        nest_asyncio.apply()
        
        # Set OpenAI API key in environment
        try:
            api_key = get_openai_api_key()
            os.environ["OPENAI_API_KEY"] = api_key
            print("✅ API Key caricata correttamente")
        except Exception as e:
            raise Exception(f"Errore nel caricamento API Key: {e}")
        
        # Create necessary directories
        create_default_directories()
        
        # Setup LangGraph workflow
        self._setup_workflow()
    
    def _setup_workflow(self):
        """Setup LangGraph workflow for conversation management"""
        self.workflow = StateGraph(state_schema=MessagesState)
        
        def call_model(state: MessagesState):
            messages = state["messages"]
            response = self.rag_service.invoke_chain(str(messages))
            return {"messages": response}
        
        # Define the node and edge
        self.workflow.add_node("model", call_model)
        self.workflow.add_edge(START, "model")
        
        # Add memory checkpoint
        memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=memory)
    
    def initialize_session(self):
        """Initialize a new session"""
        print_system_info()
        print_welcome_message()
        
        # Get session parameters
        self.participant_number, self.job_number = validate_inputs()
        
        # Setup services for this session
        self.metrics_service.setup_session(self.participant_number, self.job_number)
        self.rag_service.create_rag_chain(self.job_number)
        
        # Open camera
        self.cap = self.vision_service.open_camera()
        if not self.cap:
            print("❌ Impossibile aprire la fotocamera. Il sistema funzionerà solo in modalità audio.")
            return False
        
        return True
    
    def process_photo_request(self, query: str) -> tuple[str, str, float, float, float]:
        """
        Process photo capture request
        
        Returns:
            tuple: (processed_query, image_captured, time_for_request, time_for_dia, time_for_response)
        """
        if not self.cap:
            return query, "No", 0, 0, 0
        
        start_response_time = time.time()
        
        # Use keyboard-controlled photo capture
        image_path = self.vision_service.foto_capture_keyboard(self.cap)
        
        image_captured = "Yes" if image_path else "No"
        
        if image_path:
            # Display the captured image
            self.vision_service.display_image(image_path)
            
            # Audio feedback
            self.audio_service.text_to_audio(AUDIO_MESSAGES['photo_accept'])
            
            # Set default query for image analysis
            query = "Riconosci se l'elemento nell'immagine è un box con un numero o un oggetto, se è un oggetto dimmi dove deve essere inserito, se è un box con un numero dimmi quale oggetto inserire dentro"
        
        end_response_time = time.time()
        
        # Calculate timings (simplified for photo capture)
        time_for_request = 0
        time_for_dia = 0
        time_for_response = end_response_time - start_response_time
        
        return query, image_captured, time_for_request, time_for_dia, time_for_response
    
    def process_regular_query(self, query: str) -> tuple[str, str, str, float, float, float]:
        """
        Process regular text/voice query
        
        Returns:
            tuple: (user_request, dia_response, cleaned_response, time_for_request, time_for_dia, time_for_response)
        """
        # Invoke RAG chain
        response = self.app.invoke(
            {"messages": HumanMessage(content=query)},
            config={"configurable": {"thread_id": "10000000000"}}
        )
        
        user_request = response['messages'][-2].content
        dia_response = response['messages'][-1].content
        
        print(f"\n🧑‍💻 User: {user_request}")
        print(f"🤖 Assistente: {dia_response}")
        
        # Clean and extract response
        chiave, valore = clean_markdown(dia_response)
        cleaned_response = extract_response_value(valore)
        
        # Provide audio feedback
        start_audio_time = self.audio_service.text_to_audio(cleaned_response)
        end_audio_time = time.time()
        
        # Handle special response types
        self._handle_special_responses(chiave, valore)
        
        # Calculate timing metrics (simplified)
        time_for_request = 0
        time_for_dia = 0
        time_for_response = end_audio_time - start_audio_time
        
        return user_request, dia_response, cleaned_response, time_for_request, time_for_dia, time_for_response
    
    def _handle_special_responses(self, key: str, value: str):
        """Handle special response types that require image display"""
        completion_result = format_completion_message(key, value, self.job_number)
        
        if completion_result and len(completion_result) >= 2:
            image_path = completion_result[0]
            message = completion_result[1]
            backup_path = completion_result[2] if len(completion_result) > 2 else None
            
            if image_path and message:
                self.vision_service.show_completion_image(image_path, message, backup_path)
    
    def process_goodbye(self, query: str) -> tuple[float, float, float]:
        """
        Process goodbye/exit command
        
        Returns:
            tuple: (time_for_request, time_for_dia, time_for_response)
        """
        print("Spero di esserti stato utile! Arrivederci! 👋")
        
        start_audio_time = self.audio_service.text_to_audio(AUDIO_MESSAGES['goodbye'])
        end_audio_time = time.time()
        
        # Log goodbye interaction
        self.metrics_service.log_goodbye_interaction(
            query=query,
            goodbye_message=AUDIO_MESSAGES['goodbye'],
            time_for_request=0,
            time_for_dia=0,
            time_for_response=end_audio_time - start_audio_time
        )
        
        return 0, 0, end_audio_time - start_audio_time
    
    def run_conversation_loop(self):
        """Main conversation loop"""
        if not self.initialize_session():
            return
        
        print("\n🎙️ Sistema pronto. Inizia a parlare quando richiesto.\n")
        
        while True:
            try:
                # Wait for user speech
                start_time_call, query = self.audio_service.wait_for_speech()
                end_time_request = time.time()
                
                # Check for exit commands
                if is_stop_command(query):
                    self.process_goodbye(query)
                    break
                
                # Initialize tracking variables
                image_captured = "No"
                image_shown = "No"
                
                # Check for photo commands
                if is_photo_command(query):
                    query, image_captured, time_req, time_dia, time_resp = self.process_photo_request(query)
                    image_shown = image_captured
                    
                    # Log photo interaction
                    self.metrics_service.log_photo_interaction(time_req, time_dia, time_resp)
                
                # Process the query
                user_request, dia_response, cleaned_response, time_for_request, time_for_dia, time_for_response = self.process_regular_query(query)
                
                # Calculate actual timing metrics
                actual_time_for_request = end_time_request - start_time_call
                
                # Move captured image to archive
                self.metrics_service.move_captured_image("captured_image.jpg", "content/archivio")
                
                # Log the interaction
                self.metrics_service.log_interaction(
                    request=user_request,
                    response=dia_response,
                    time_for_request=actual_time_for_request,
                    time_for_dia=time_for_dia,
                    time_for_response=time_for_response,
                    image_captured=image_captured,
                    image_shown=image_shown
                )
                
            except KeyboardInterrupt:
                print("\n🛑 Interruzione utente. Chiusura sistema...")
                break
            except Exception as e:
                print(f"❌ Errore durante l'elaborazione: {e}")
                continue
        
        # Cleanup
        self.cleanup()
    
    def cleanup(self):
        """Cleanup system resources"""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        
        # Print session statistics
        stats = self.metrics_service.get_session_stats()
        if stats.get("total_interactions", 0) > 0:
            print(f"\n📊 Statistiche sessione:")
            print(f"   - Interazioni totali: {stats['total_interactions']}")
            print(f"   - Immagini catturate: {stats.get('images_captured', 0)}")
            print(f"   - Tempo medio richiesta: {stats.get('avg_request_time', 0):.2f}s")
            print(f"   - Tempo medio risposta: {stats.get('avg_response_time', 0):.2f}s")
        
        print("\n✅ Sistema chiuso correttamente.")


def main():
    """Main entry point"""
    try:
        # Create and run DIA system
        dia_system = DIASystem()
        dia_system.run_conversation_loop()
        
    except Exception as e:
        print(f"❌ Errore critico del sistema: {e}")
        print("Verifica la configurazione e riprova.")


if __name__ == "__main__":
    main()
