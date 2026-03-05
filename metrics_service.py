"""
Metrics Service for DIA (Digital Intelligent Assistant)
Handles logging and metrics collection
"""
import os
import time
import shutil
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any

from config import EXCEL_FILENAME, EXCEL_COLUMNS


class MetricsService:
    """Service for handling metrics collection and logging"""
    
    def __init__(self, excel_filename: str = EXCEL_FILENAME):
        self.excel_filename = excel_filename
        self.participant_number = ""
        self.job_number = ""
        self.request_counter = 1
        self._initialize_excel()
    
    def _initialize_excel(self):
        """Initialize Excel file if it doesn't exist"""
        if not os.path.exists(self.excel_filename):
            df = pd.DataFrame(columns=EXCEL_COLUMNS)
            df.to_excel(self.excel_filename, index=False)
    
    def setup_session(self, participant_number: str, job_number: str):
        """Setup session parameters"""
        self.participant_number = participant_number
        self.job_number = job_number
        self.request_counter = 1
    
    def get_interaction_code(self) -> str:
        """Generate interaction code"""
        interaction_code = f"{self.participant_number}{self.job_number}{self.request_counter:02d}"
        self.request_counter += 1
        return interaction_code
    
    def log_interaction(self, 
                       request: str,
                       response: str,
                       time_for_request: float,
                       time_for_dia: float,
                       time_for_response: float,
                       image_captured: str = "No",
                       image_shown: str = "No") -> None:
        """
        Log an interaction to Excel
        
        Args:
            request: User request text
            response: DIA response text
            time_for_request: Time between call and end of request
            time_for_dia: Time between end of request and start of response
            time_for_response: Time between start and end of response
            image_captured: Whether image was captured ("Yes"/"No")
            image_shown: Whether image was shown ("Yes"/"No")
        """
        interaction_code = f"{self.participant_number}{self.job_number}{self.request_counter:02d}"
        self.request_counter += 1
        
        # Read existing data
        df = pd.read_excel(self.excel_filename)
        
        # Create new row
        new_row = {
            "Participant": self.participant_number,
            "Job": self.job_number,
            "Request": request,
            "DIA Answer": response,
            "Interaction Code": interaction_code,
            "Time between call and end of request (sec)": round(time_for_request, 2),
            "Time between end of request and start of response (sec)": round(time_for_dia, 2),
            "Time between start and end of response (sec)": round(time_for_response, 2),
            "Image captured?": image_captured,
            "Image shown?": image_shown,
        }
        
        # Add row and save
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(self.excel_filename, index=False)
        
        print("✅ Dati salvati su Excel.")
    
    def update_last_interaction_timing(self, time_for_dia: float = None, time_for_response: float = None) -> None:
        """
        Update the timing metrics for the last interaction (for audio playback timing)
        
        Args:
            time_for_dia: Time between end of request and start of audio response (None = don't update)
            time_for_response: Time between start and end of audio response (audio duration)
        """
        try:
            print(f"\n🔧 DEBUG: Inizio aggiornamento timing...")
            print(f"🔧 DEBUG: File Excel: {self.excel_filename}")
            print(f"🔧 DEBUG: Participant: {self.participant_number}, Job: {self.job_number}")
            print(f"🔧 DEBUG: Time G to update: {time_for_dia}, Time H to update: {time_for_response}")
            
            # Read existing data
            df = pd.read_excel(self.excel_filename)
            print(f"🔧 DEBUG: Excel loaded, total rows: {len(df)}")
            
            if df.empty:
                print("⚠️ No interactions to update")
                return
            
            # Convert to same type for comparison (both to int)
            participant_to_find = int(self.participant_number)
            job_to_find = int(self.job_number)
            
            print(f"🔧 DEBUG: Looking for Participant={participant_to_find} (type: {type(participant_to_find)}), Job={job_to_find} (type: {type(job_to_find)})")
            print(f"🔧 DEBUG: Excel Participant type: {df['Participant'].dtype}, Job type: {df['Job'].dtype}")
            
            # Get the last row for this session
            session_data = df[
                (df['Participant'] == participant_to_find) & 
                (df['Job'] == job_to_find)
            ]
            
            print(f"🔧 DEBUG: Rows for this session: {len(session_data)}")
            
            if session_data.empty:
                print("⚠️ No interactions found for this session")
                print(f"🔧 DEBUG: Available Participants: {df['Participant'].unique()}")
                print(f"🔧 DEBUG: Available Jobs: {df['Job'].unique()}")
                return
            
            # Get the index of the last interaction for this session
            last_index = session_data.index[-1]
            print(f"🔧 DEBUG: Last interaction index: {last_index}")
            print(f"🔧 DEBUG: Current values - Time G: {df.at[last_index, 'Time between end of request and start of response (sec)']}, Time H: {df.at[last_index, 'Time between start and end of response (sec)']}")
            
            # Update timing columns
            if time_for_dia is not None:
                df.at[last_index, "Time between end of request and start of response (sec)"] = round(time_for_dia, 2)
                print(f"🔧 DEBUG: Updated Time G to {round(time_for_dia, 2)}")
            
            if time_for_response is not None:
                df.at[last_index, "Time between start and end of response (sec)"] = round(time_for_response, 2)
                print(f"🔧 DEBUG: Updated Time H to {round(time_for_response, 2)}")
            
            # Save updated data
            print(f"🔧 DEBUG: Saving to Excel...")
            df.to_excel(self.excel_filename, index=False)
            print(f"🔧 DEBUG: Excel saved successfully!")
            
            update_msg = []
            if time_for_dia is not None:
                update_msg.append(f"Time G={time_for_dia:.2f}s")
            if time_for_response is not None:
                update_msg.append(f"Time H={time_for_response:.2f}s")
            
            print(f"✅ Timing aggiornato: {', '.join(update_msg)}\n")
            
        except Exception as e:
            import traceback
            print(f"❌ Errore nell'aggiornamento timing: {e}")
            print(f"❌ Traceback completo:")
            traceback.print_exc()
    
    def log_photo_interaction(self,
                            time_for_request: float,
                            time_for_dia: float,
                            time_for_response: float,
                            message: str = "scatto foto") -> None:
        """Log a photo capture interaction"""
        self.log_interaction(
            request=message,
            response="apertura fotocamera",
            time_for_request=time_for_request,
            time_for_dia=time_for_dia,
            time_for_response=time_for_response,
            image_captured="Yes",
            image_shown="Yes"
        )
    
    def log_goodbye_interaction(self,
                              query: str,
                              goodbye_message: str,
                              time_for_request: float,
                              time_for_dia: float,
                              time_for_response: float) -> None:
        """Log a goodbye interaction"""
        interaction_code = f"{self.participant_number}{self.job_number}{self.request_counter:02d}"
        self.request_counter += 1
        
        df = pd.read_excel(self.excel_filename)
        new_row = {
            "Participant": self.participant_number,
            "Job": self.job_number,
            "Request": query,
            "DIA Answer": goodbye_message,
            "Interaction Code": interaction_code,
            "Time between call and end of request (sec)": time_for_request,
            "Time between end of request and start of response (sec)": time_for_dia,
            "Time between start and end of response (sec)": time_for_response,
            "Image captured?": None,
            "Image shown?": None
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(self.excel_filename, index=False)
        print("✅ Dati salvati su Excel.")
    
    def move_captured_image(self, 
                          source_path: str = "captured_image.jpg", 
                          archive_folder: str = "content/archivio") -> Optional[str]:
        """
        Move captured image to archive folder
        
        Args:
            source_path: Path of the image to move
            archive_folder: Destination folder
        
        Returns:
            str or None: The new path of the image, or None if move fails
        """
        try:
            # Check if file exists
            if not os.path.exists(source_path):
                print(f"⚠️ File {source_path} non trovato.")
                return None
            
            # Create destination folder if it doesn't exist
            if not os.path.exists(archive_folder):
                os.makedirs(archive_folder)
                print(f"✅ Creata cartella {archive_folder}")
            
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"image_{timestamp}.jpg"
            destination_path = os.path.join(archive_folder, filename)
            
            # Move file
            shutil.move(source_path, destination_path)
            print(f"✅ Immagine spostata in {destination_path}")
            
            return destination_path
        
        except Exception as e:
            print(f"❌ Errore durante lo spostamento dell'immagine: {e}")
            return None
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for current session"""
        try:
            df = pd.read_excel(self.excel_filename)
            session_data = df[
                (df['Participant'] == self.participant_number) & 
                (df['Job'] == self.job_number)
            ]
            
            if session_data.empty:
                return {"total_interactions": 0}
            
            stats = {
                "total_interactions": len(session_data),
                "avg_request_time": session_data["Time between call and end of request (sec)"].mean(),
                "avg_response_time": session_data["Time between start and end of response (sec)"].mean(),
                "avg_latency": session_data["Time between end of request and start of response (sec)"].mean(),
                "images_captured": len(session_data[session_data["Image captured?"] == "Yes"]),
                "images_shown": len(session_data[session_data["Image shown?"] == "Yes"])
            }
            
            return stats
        
        except Exception as e:
            print(f"Error getting session stats: {e}")
            return {"error": str(e)}
    
    def export_session_data(self, output_file: Optional[str] = None) -> str:
        """
        Export current session data to a separate file
        
        Args:
            output_file: Output filename (optional)
            
        Returns:
            str: Path to exported file
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"session_{self.participant_number}_{self.job_number}_{timestamp}.xlsx"
        
        try:
            df = pd.read_excel(self.excel_filename)
            session_data = df[
                (df['Participant'] == self.participant_number) & 
                (df['Job'] == self.job_number)
            ]
            
            session_data.to_excel(output_file, index=False)
            print(f"✅ Dati sessione esportati in: {output_file}")
            return output_file
        
        except Exception as e:
            print(f"❌ Errore nell'esportazione: {e}")
            return ""


class TimeTracker:
    """Helper class for tracking timing metrics"""
    
    def __init__(self):
        self.start_time = 0
        self.end_request_time = 0
        self.start_response_time = 0
        self.end_response_time = 0
    
    def start_call(self) -> float:
        """Mark the start of a call"""
        self.start_time = time.time()
        return self.start_time
    
    def end_request(self) -> float:
        """Mark the end of request input"""
        self.end_request_time = time.time()
        return self.end_request_time
    
    def start_response(self) -> float:
        """Mark the start of response generation"""
        self.start_response_time = time.time()
        return self.start_response_time
    
    def end_response(self) -> float:
        """Mark the end of response output"""
        self.end_response_time = time.time()
        return self.end_response_time
    
    def get_timings(self) -> tuple[float, float, float]:
        """
        Get all timing metrics
        
        Returns:
            tuple: (request_duration, latency, response_duration)
        """
        request_duration = self.end_request_time - self.start_time
        latency = self.start_response_time - self.end_request_time
        response_duration = self.end_response_time - self.start_response_time
        
        return request_duration, latency, response_duration


# Utility functions
def get_metrics_service(excel_filename: str = EXCEL_FILENAME) -> MetricsService:
    """Get a MetricsService instance"""
    return MetricsService(excel_filename)

def get_time_tracker() -> TimeTracker:
    """Get a TimeTracker instance"""
    return TimeTracker()
