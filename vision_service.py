"""
Vision Service for DIA (Digital Intelligent Assistant)
Handles camera operations and image processing
"""
import os
import cv2
import time
import keyboard
import speech_recognition as sr
from typing import Optional

from config import AUDIO_MESSAGES


class VisionService:
    """Service for handling camera and image operations"""
    
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.recognizer = sr.Recognizer()
    
    def open_camera(self) -> Optional[cv2.VideoCapture]:
        """
        Open camera capture
        
        Returns:
            cv2.VideoCapture or None: Camera capture object or None if failed
        """
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print("❌ Errore: impossibile aprire la fotocamera.")
            return None
        return cap
    
    def foto_capture_voice(self, cap: cv2.VideoCapture) -> bool:
        """
        Capture photo using voice commands
        
        Args:
            cap: OpenCV VideoCapture object
            
        Returns:
            bool: True if photo was captured successfully
        """
        if not cap.isOpened():
            print("ERRORE: non è possibile aprire la webcam\n")
            return False
        
        print("Apertura fotocamera...")
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print("ERRORE: non è stato possibile catturare l'immagine\n")
                break
            
            # Display the frame
            cv2.imshow('Webcam', frame)
            
            # Wait for voice command
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source)
                print("In attesa del comando vocale...\n")
                
                try:
                    audio = self.recognizer.listen(source)
                    command = self.recognizer.recognize_google(audio, language="it-IT").lower()
                    print(f"Hai detto: {command}\n")
                    
                    if any(word in command for word in ["foto", "scatta", "scatta la foto"]):
                        print("Cattura immagine in corso...\n")
                        cv2.imwrite('captured_image.jpg', frame)
                        print("Immagine salvata con successo!\n")
                        break
                    
                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    print("Could not request results from Google Speech Recognition service\n")
            
            # Check for 'q' key to exit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Uscendo...\n")
                break
        
        cv2.destroyAllWindows()
        return True
    
    def foto_capture_keyboard(self, cap: cv2.VideoCapture) -> Optional[str]:
        """
        Capture a photo using keyboard controls:
        - SPACE or F: Take/retake photo
        - ENTER: Confirm and save photo
        
        Args:
            cap: OpenCV VideoCapture object
            
        Returns:
            str or None: Path to saved image or None if failed
        """
        print("📸 " + AUDIO_MESSAGES['photo_instructions'])
        
        photo_taken = False
        photo_confirmed = False
        frame = None
        
        while not photo_confirmed:
            # Capture frame
            ret, current_frame = cap.read()
            
            if not ret:
                print(AUDIO_MESSAGES['camera_error'])
                return None
            
            # Display appropriate frame
            if not photo_taken:
                display_frame = current_frame.copy()
                cv2.putText(display_frame, "Premi SPAZIO o F per scattare", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                display_frame = frame.copy()
                cv2.putText(display_frame, "Premi INVIO per confermare o SPAZIO/F per riprovare", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Display the frame
            cv2.imshow('Webcam', display_frame)
            cv2.waitKey(1)
            
            # Check for keyboard input
            if keyboard.is_pressed('space') or keyboard.is_pressed('f'):
                if not photo_taken:
                    print(AUDIO_MESSAGES['photo_taken'])
                else:
                    print(AUDIO_MESSAGES['photo_retake'])
                
                frame = current_frame.copy()
                photo_taken = True
                time.sleep(0.5)  # Prevent multiple captures
                
            elif keyboard.is_pressed('enter') and photo_taken:
                print(AUDIO_MESSAGES['photo_confirmed'])
                cv2.imwrite('captured_image.jpg', frame)
                photo_confirmed = True
                time.sleep(0.5)
            
            # Add small sleep to prevent high CPU usage
            time.sleep(0.05)
        
        cv2.destroyAllWindows()
        print("✅ " + AUDIO_MESSAGES['photo_saved'])
        return 'captured_image.jpg'
    
    def display_image(self, image_path: str) -> bool:
        """
        Display an image in a window
        
        Args:
            image_path (str): Path to the image file
            
        Returns:
            bool: True if image was displayed successfully
        """
        img = cv2.imread(image_path)
        if img is None:
            print("⚠️ Immagine non trovata.")
            return False
        else:
            cv2.imshow("Immagine Richiesta", img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            return True
    
    def show_completion_image(self, image_path: str, message: str = "Lavoro completato! Premi INVIO per continuare.", backup_image_path: Optional[str] = None) -> None:
        """
        Show an image and wait for user to press ENTER to continue
        
        Args:
            image_path (str): Path to the main image
            message (str): Message to display
            backup_image_path (str, optional): Backup image path if main fails
        """
        try:
            # Load main image
            img = cv2.imread(image_path)
            
            # Try backup image if main fails
            if img is None and backup_image_path is not None:
                print(f"⚠️ Impossibile caricare l'immagine principale: {image_path}")
                print(f"Tentativo con l'immagine di backup: {backup_image_path}")
                img = cv2.imread(backup_image_path)
            
            # If both images fail
            if img is None:
                error_msg = f"⚠️ Impossibile caricare l'immagine: {image_path}"
                if backup_image_path:
                    error_msg += f" e l'immagine di backup: {backup_image_path}"
                print(error_msg)
                input("Premi INVIO per continuare...")
                return
            
            # Create display copy and add text
            display_img = img.copy()
            cv2.putText(display_img, message, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Create window and resize appropriately
            window_name = "Completamento"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            
            h, w = img.shape[:2]
            display_width = min(w, 1024)
            display_height = int(h * (display_width / w))
            cv2.resizeWindow(window_name, display_width, display_height)
            
            # Show image
            cv2.imshow(window_name, display_img)
            cv2.waitKey(1)
            
            print(f"\n{message}")
            
            # Wait for ENTER key
            waiting = True
            while waiting:
                key = cv2.waitKey(100) & 0xFF
                if key == 13 or key == 27:  # ENTER or ESC
                    waiting = False
            
            cv2.destroyWindow(window_name)
            
        except Exception as e:
            print(f"⚠️ Errore durante la visualizzazione dell'immagine: {e}")
            input("Premi INVIO per continuare...")


# Utility function for backward compatibility
def get_vision_service(camera_index: int = 0) -> VisionService:
    """Get a VisionService instance"""
    return VisionService(camera_index)
