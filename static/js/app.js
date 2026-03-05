/**
 * DIA Web Interface JavaScript
 * Handles camera, chat, and WebSocket communication
 */

class DIAWebInterface {
    constructor() {
        this.socket = null;
        this.sessionId = null;
        this.cameraStream = null;
        this.isSessionActive = false;
        this.capturedImageData = null;
        
        // Voice recognition
        this.recognition = null;
        this.isRecording = false;
        this.voiceOutputEnabled = true;
        this.currentAudio = null;
        
        this.initializeElements();
        this.initializeSpeechRecognition();
        this.bindEvents();
        this.enumerateCameras();
        this.enumerateMicrophones();
        this.showSessionModal();
    }
    
    initializeElements() {
        // Modals
        this.sessionModal = new bootstrap.Modal(document.getElementById('sessionModal'));
        
        // Form elements
        this.sessionForm = document.getElementById('sessionForm');
        this.participantInput = document.getElementById('participantNumber');
        this.jobSelect = document.getElementById('jobNumber');
        this.startSessionBtn = document.getElementById('startSessionBtn');
        
        // Camera elements
        this.cameraFeed = document.getElementById('cameraFeed');
        this.captureCanvas = document.getElementById('captureCanvas');
        this.toggleCameraBtn = document.getElementById('toggleCameraBtn');
        this.captureBtn = document.getElementById('captureBtn');
        this.sendImageBtn = document.getElementById('sendImageBtn');
        this.cameraStatus = document.getElementById('cameraStatus');
        this.cameraSelect = document.getElementById('cameraSelect');
        
        // Camera management
        this.availableCameras = [];
        this.selectedCameraId = null;
        
        // Microphone management
        this.availableMicrophones = [];
        this.selectedMicrophoneId = null;
        this.microphoneSelect = document.getElementById('microphoneSelect');
        
        // Image preview elements
        this.imagePreview = document.getElementById('imagePreview');
        this.capturedImage = document.getElementById('capturedImage');
        this.retakeBtn = document.getElementById('retakeBtn');
        this.confirmImageBtn = document.getElementById('confirmImageBtn');
        
        // Chat elements
        this.chatMessages = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendMessageBtn = document.getElementById('sendMessageBtn');
        
        // Voice elements
        this.voiceInputBtn = document.getElementById('voiceInputBtn');
        this.voiceOutputToggle = document.getElementById('voiceOutputToggle');
        this.voiceRecordingIndicator = document.getElementById('voiceRecordingIndicator');
        this.inputModeText = document.getElementById('inputModeText');
        
        // Interface elements
        this.mainInterface = document.getElementById('mainInterface');
        this.sessionInfo = document.getElementById('sessionInfo');
        this.endSessionBtn = document.getElementById('endSessionBtn');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        
        // ⏱️ Voice timing tracking
        this.voiceRecordingStartTime = null;
        this.voiceRecordingEndTime = null;
        this.audioResponseStartTime = null;
        this.audioResponseEndTime = null;
        this.currentInteractionCode = null;  // Track current interaction for metrics update
    }
    
    initializeSpeechRecognition() {
        console.log('🔧 Initializing Speech Recognition...');
        
        // Check if browser supports speech recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            console.warn('❌ Speech recognition not supported in this browser');
            // Hide voice input button if not supported
            if (this.voiceInputBtn) {
                this.voiceInputBtn.style.display = 'none';
            }
            return;
        }
        
        console.log('✅ Speech Recognition API available');
        
        this.recognition = new SpeechRecognition();
        this.recognition.lang = 'it-IT';
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        
        console.log('✅ Speech Recognition initialized');
        
        this.recognition.onstart = () => {
            // ⏱️ Track voice recording start time
            this.voiceRecordingStartTime = Date.now() / 1000; // Convert to seconds
            console.log('🎤 Voice recording started at:', this.voiceRecordingStartTime);
            
            this.isRecording = true;
            this.voiceInputBtn.classList.add('recording');
            this.voiceRecordingIndicator.style.display = 'block';
            this.inputModeText.innerHTML = '<i class="fas fa-microphone me-1"></i>Modalità Vocale';
        };
        
        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            this.messageInput.value = transcript;
            console.log('Voice input:', transcript);
        };
        
        this.recognition.onend = () => {
            // ⏱️ Track voice recording end time
            this.voiceRecordingEndTime = Date.now() / 1000; // Convert to seconds
            const recordingDuration = this.voiceRecordingEndTime - this.voiceRecordingStartTime;
            console.log('🎤 Voice recording ended at:', this.voiceRecordingEndTime);
            console.log('⏱️ Recording duration:', recordingDuration.toFixed(2) + 's');
            
            this.isRecording = false;
            this.voiceInputBtn.classList.remove('recording');
            this.voiceRecordingIndicator.style.display = 'none';
            this.inputModeText.innerHTML = '<i class="fas fa-keyboard me-1"></i>Modalità Testo';
            
            // Auto-send if there's a message
            if (this.messageInput.value.trim()) {
                this.sendMessage();
            }
        };
        
        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.isRecording = false;
            this.voiceInputBtn.classList.remove('recording');
            this.voiceRecordingIndicator.style.display = 'none';
            
            if (event.error === 'no-speech') {
                this.showToast('Nessun audio rilevato. Riprova.', 'warning');
            } else {
                this.showToast('Errore nel riconoscimento vocale', 'error');
            }
        };
    }
    
    bindEvents() {
        // Session events
        this.startSessionBtn.addEventListener('click', () => this.startSession());
        this.endSessionBtn.addEventListener('click', () => this.endSession());
        
        // Camera events
        this.toggleCameraBtn.addEventListener('click', () => this.toggleCamera());
        this.captureBtn.addEventListener('click', () => this.capturePhoto());
        this.sendImageBtn.addEventListener('click', () => this.sendImageWithMessage());
        this.retakeBtn.addEventListener('click', () => this.retakePhoto());
        this.confirmImageBtn.addEventListener('click', () => this.confirmImage());
        this.cameraSelect.addEventListener('change', () => this.switchCamera());
        this.microphoneSelect.addEventListener('change', () => this.switchMicrophone());
        
        // Chat events
        this.sendMessageBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Voice events
        this.voiceInputBtn.addEventListener('click', () => this.toggleVoiceInput());
        this.voiceOutputToggle.addEventListener('change', (e) => {
            this.voiceOutputEnabled = e.target.checked;
            const status = this.voiceOutputEnabled ? 'attivato' : 'disattivato';
            this.showToast(`Audio risposta ${status}`, 'info');
        });
        
        // Form validation
        [this.participantInput, this.jobSelect].forEach(input => {
            input.addEventListener('input', () => this.validateSessionForm());
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Check if user is not typing in an input field
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            // F key to capture photo (when camera is active and no photo captured)
            if ((e.key === 'f' || e.key === 'F') && this.cameraStream && !this.capturedImageData) {
                e.preventDefault();
                this.capturePhoto();
            }
            // Space key to confirm captured image
            else if (e.key === ' ' && this.capturedImageData) {
                e.preventDefault();
                this.confirmImage();
            }
            // R key to retake photo
            else if ((e.key === 'r' || e.key === 'R') && this.capturedImageData) {
                e.preventDefault();
                this.retakePhoto();
            }
            // A key to toggle voice input
            else if (e.key === 'a' || e.key === 'A') {
                e.preventDefault();
                this.toggleVoiceInput();
            }
        });
    }
    
    async toggleVoiceInput() {
        console.log('🎤 toggleVoiceInput called');
        
        if (!this.recognition) {
            console.error('❌ Recognition not initialized');
            this.showToast('Riconoscimento vocale non supportato in questo browser', 'error');
            return;
        }
        
        if (this.isRecording) {
            console.log('🛑 Stopping recording...');
            this.recognition.stop();
        } else {
            console.log('🎙️ Starting recording...');
            
            // Request microphone access with selected device
            try {
                // Build audio constraints
                const audioConstraints = {};
                
                // Use selected microphone if available
                if (this.selectedMicrophoneId) {
                    audioConstraints.deviceId = { exact: this.selectedMicrophoneId };
                    console.log('🎤 Using selected microphone:', this.selectedMicrophoneId);
                } else {
                    console.log('🎤 Using default microphone');
                }
                
                // Request microphone access to ensure the selected device is used
                // Note: Web Speech API doesn't directly support device selection,
                // but requesting getUserMedia first helps the browser use the right device
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: audioConstraints
                });
                
                // Stop the stream immediately as we only needed it to set the device
                stream.getTracks().forEach(track => track.stop());
                
                // Now start speech recognition
                this.recognition.start();
                
            } catch (error) {
                console.error('❌ Error starting recognition:', error);
                if (error.name === 'NotFoundError') {
                    this.showToast('Microfono selezionato non trovato. Prova con un altro microfono.', 'error');
                } else if (error.name === 'NotAllowedError') {
                    this.showToast('Permesso microfono negato. Abilita l\'accesso al microfono.', 'error');
                } else {
                    this.showToast('Errore nell\'avvio del microfono: ' + error.message, 'error');
                }
            }
        }
    }
    
    async playVoiceResponse(text) {
        console.log('🔊 playVoiceResponse called with text:', text?.substring(0, 50) + '...');
        
        // Stop any currently playing audio
        if (this.currentAudio) {
            console.log('🛑 Stopping current audio');
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        
        if (!this.voiceOutputEnabled) {
            console.log('🔇 Voice output disabled');
            return;
        }
        
        if (!text) {
            console.log('⚠️ No text provided for TTS');
            return;
        }
        
        try {
            console.log('📡 Requesting TTS from backend...');
            
            // Show speaking indicator
            this.showSpeakingIndicator();
            
            // Request TTS from backend
            const response = await fetch('/api/text_to_speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ text: text })
            });
            
            if (!response.ok) {
                throw new Error('TTS request failed with status: ' + response.status);
            }
            
            console.log('✅ TTS response received, creating audio...');
            
            // Get audio blob
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            
            // Play audio
            this.currentAudio = new Audio(audioUrl);
            
            this.currentAudio.onended = () => {
                // ⏱️ Track audio end time
                this.audioResponseEndTime = Date.now() / 1000;
                const audioDuration = this.audioResponseEndTime - this.audioResponseStartTime;
                console.log('✅ Audio playback ended at:', this.audioResponseEndTime);
                console.log('⏱️ Audio duration:', audioDuration.toFixed(2) + 's');
                
                // Send timing metrics to backend
                this.sendAudioTimingMetrics();
                
                this.hideSpeakingIndicator();
                URL.revokeObjectURL(audioUrl);
                this.currentAudio = null;
            };
            
            this.currentAudio.onerror = (e) => {
                console.error('❌ Error playing audio:', e);
                this.hideSpeakingIndicator();
            };
            
            // ⏱️ Track audio start time
            this.audioResponseStartTime = Date.now() / 1000;
            console.log('🔊 Audio playback started at:', this.audioResponseStartTime);
            
            await this.currentAudio.play();
            console.log('🔊 Audio playing...');
            
        } catch (error) {
            console.error('❌ Error in playVoiceResponse:', error);
            this.hideSpeakingIndicator();
            this.showToast('Errore riproduzione audio: ' + error.message, 'error');
        }
    }
    
    async sendAudioTimingMetrics() {
        // Send audio timing metrics to backend for metrics update
        
        // We need at least audio start and end times
        if (!this.audioResponseStartTime || !this.audioResponseEndTime) {
            console.log('⏱️ No audio timing to send (missing audio data)');
            return;
        }
        
        // For voice input: use voice recording end time
        // For text input: voice_recording_end will be sent as null, backend will handle it
        const voiceRecordingEnd = this.voiceRecordingEndTime || null;
        
        const timeH = this.audioResponseEndTime - this.audioResponseStartTime;
        
        if (voiceRecordingEnd) {
            const timeG = this.audioResponseStartTime - voiceRecordingEnd;
            console.log('⏱️ Sending audio timing metrics (VOICE INPUT):', {
                voice_recording_end: voiceRecordingEnd,
                audio_response_start: this.audioResponseStartTime,
                audio_response_end: this.audioResponseEndTime,
                time_G: timeG.toFixed(2) + 's',
                time_H: timeH.toFixed(2) + 's'
            });
        } else {
            console.log('⏱️ Sending audio timing metrics (TEXT INPUT):', {
                audio_response_start: this.audioResponseStartTime,
                audio_response_end: this.audioResponseEndTime,
                time_H: timeH.toFixed(2) + 's'
            });
        }
        
        try {
            const response = await fetch('/api/update_audio_timing', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    voice_recording_end: this.voiceRecordingEndTime,
                    audio_response_start: this.audioResponseStartTime,
                    audio_response_end: this.audioResponseEndTime
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('✅ Audio timing metrics updated successfully');
            } else {
                console.error('❌ Failed to update audio timing:', data.error);
            }
        } catch (error) {
            console.error('❌ Error sending audio timing metrics:', error);
        } finally {
            // ✅ Reset voice timing for next message ONLY after audio timing is sent
            this.voiceRecordingStartTime = null;
            this.voiceRecordingEndTime = null;
            this.audioResponseStartTime = null;
            this.audioResponseEndTime = null;
        }
    }
    
    showSpeakingIndicator() {
        // Add speaking indicator to last assistant message
        const messages = this.chatMessages.querySelectorAll('.assistant-message');
        if (messages.length > 0) {
            const lastMessage = messages[messages.length - 1];
            const indicator = document.createElement('div');
            indicator.className = 'speaking-indicator mt-2';
            indicator.id = 'speakingIndicator';
            indicator.innerHTML = `
                <small class="text-muted me-2">
                    <i class="fas fa-volume-up me-1"></i>
                    Riproduzione audio
                </small>
                <div class="speaking-bar"></div>
                <div class="speaking-bar"></div>
                <div class="speaking-bar"></div>
            `;
            lastMessage.querySelector('.message-content').appendChild(indicator);
        }
    }
    
    hideSpeakingIndicator() {
        const indicator = document.getElementById('speakingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    showSessionModal() {
        this.sessionModal.show();
    }
    
    validateSessionForm() {
        const isValid = this.participantInput.value.trim() && this.jobSelect.value;
        this.startSessionBtn.disabled = !isValid;
    }
    
    async startSession() {
        const participantNumber = this.participantInput.value.trim();
        const jobNumber = this.jobSelect.value;
        
        if (!participantNumber || !jobNumber) {
            this.showToast('Compila tutti i campi', 'error');
            return;
        }
        
        this.showLoading(true);
        
        try {
            const response = await fetch('/api/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    participant_number: participantNumber,
                    job_number: jobNumber
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                this.isSessionActive = true;
                
                // Update UI
                this.sessionInfo.textContent = `Partecipante ${participantNumber} - Job ${jobNumber}`;
                this.endSessionBtn.style.display = 'inline-block';
                
                // Hide modal and show main interface
                this.sessionModal.hide();
                this.mainInterface.style.display = 'flex';
                
                // Add welcome message
                this.addSystemMessage(data.message);
                
                // Show success message with Excel filename
                const excelFile = data.excel_filename || 'DIA_metrics.xlsx';
                console.log(`📊 Session Excel file created: ${excelFile}`);
                this.showToast(`Sessione inizializzata! File metriche: ${excelFile}`, 'success');
            } else {
                this.showToast(data.error || 'Errore nell\'inizializzazione', 'error');
            }
        } catch (error) {
            console.error('Error starting session:', error);
            this.showToast('Errore di connessione', 'error');
        } finally {
            this.showLoading(false);
        }
    }
    
    async endSession() {
        if (!this.isSessionActive) return;
        
        try {
            const response = await fetch('/api/end_session', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Download metrics file before resetting UI
                this.downloadMetricsFile();
                
                // Reset UI
                this.isSessionActive = false;
                this.sessionId = null;
                this.mainInterface.style.display = 'none';
                this.endSessionBtn.style.display = 'none';
                this.sessionInfo.textContent = '';
                
                // Stop camera if active
                if (this.cameraStream) {
                    this.stopCamera();
                }
                
                // Clear chat
                this.chatMessages.innerHTML = '';
                
                // Show session modal again
                this.showSessionModal();
                
                // Show success message with filename
                const filename = data.excel_filename || 'DIA_metrics.xlsx';
                this.showToast(`Sessione terminata - Download di ${filename} in corso...`, 'success');
                
                // Show stats if available
                if (data.stats && data.stats.total_interactions > 0) {
                    this.showSessionStats(data.stats);
                }
            }
        } catch (error) {
            console.error('Error ending session:', error);
            this.showToast('Errore nella chiusura della sessione', 'error');
        }
    }
    
    downloadMetricsFile() {
        // Create a temporary link to download the metrics file
        console.log('📥 Downloading metrics file...');
        
        const link = document.createElement('a');
        link.href = '/api/download_metrics';
        link.download = 'DIA_metrics.xlsx';
        
        // Append to body, click, and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        console.log('✅ Metrics download initiated');
    }
    
    async toggleCamera() {
        if (this.cameraStream) {
            this.stopCamera();
        } else {
            await this.startCamera();
        }
    }
    
    async startCamera() {
        try {
            // Build video constraints
            const videoConstraints = {
                width: { ideal: 1280 },
                height: { ideal: 720 }
            };
            
            // Use selected camera if available, otherwise use facing mode
            if (this.selectedCameraId) {
                videoConstraints.deviceId = { exact: this.selectedCameraId };
            } else {
                videoConstraints.facingMode = 'environment'; // Prefer back camera
            }
            
            this.cameraStream = await navigator.mediaDevices.getUserMedia({
                video: videoConstraints,
                audio: false
            });
            
            this.cameraFeed.srcObject = this.cameraStream;
            
            // Update UI
            this.toggleCameraBtn.innerHTML = '<i class="fas fa-video-slash me-1"></i>Disattiva Camera';
            this.toggleCameraBtn.classList.remove('btn-primary');
            this.toggleCameraBtn.classList.add('btn-danger');
            this.captureBtn.disabled = false;
            this.cameraStatus.style.display = 'none';
            
            // Show keyboard shortcuts info
            this.showToast('📸 Premi F per scattare | SPAZIO per confermare | R per rifare', 'info');
            
        } catch (error) {
            console.error('Error accessing camera:', error);
            this.showToast('Errore nell\'accesso alla fotocamera', 'error');
            this.updateCameraStatus('Errore fotocamera', 'error');
        }
    }
    
    stopCamera() {
        if (this.cameraStream) {
            this.cameraStream.getTracks().forEach(track => track.stop());
            this.cameraStream = null;
            this.cameraFeed.srcObject = null;
        }
        
        // Update UI
        this.toggleCameraBtn.innerHTML = '<i class="fas fa-video me-1"></i>Attiva Camera';
        this.toggleCameraBtn.classList.remove('btn-danger');
        this.toggleCameraBtn.classList.add('btn-primary');
        this.captureBtn.disabled = true;
        this.cameraStatus.style.display = 'block';
        this.updateCameraStatus('Clicca "Attiva Camera" per iniziare');
    }
    
    async enumerateCameras() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.availableCameras = devices.filter(device => device.kind === 'videoinput');
            
            console.log('📹 Available cameras:', this.availableCameras);
            
            // Populate camera select
            this.cameraSelect.innerHTML = '';
            
            if (this.availableCameras.length === 0) {
                this.cameraSelect.innerHTML = '<option value="">Nessuna fotocamera trovata</option>';
                return;
            }
            
            this.availableCameras.forEach((camera, index) => {
                const option = document.createElement('option');
                option.value = camera.deviceId;
                
                // Generate friendly name
                let label = camera.label || `Fotocamera ${index + 1}`;
                
                // Try to detect camera type
                if (label.toLowerCase().includes('back') || label.toLowerCase().includes('rear')) {
                    label += ' 📷 (Posteriore)';
                } else if (label.toLowerCase().includes('front')) {
                    label += ' 🤳 (Frontale)';
                } else if (label.toLowerCase().includes('usb') || label.toLowerCase().includes('external')) {
                    label += ' 🎥 (Esterna)';
                }
                
                option.textContent = label;
                this.cameraSelect.appendChild(option);
            });
            
            // Select first camera by default
            if (this.availableCameras.length > 0) {
                this.selectedCameraId = this.availableCameras[0].deviceId;
            }
            
        } catch (error) {
            console.error('Error enumerating cameras:', error);
            this.cameraSelect.innerHTML = '<option value="">Errore rilevamento fotocamere</option>';
        }
    }
    
    async switchCamera() {
        const wasActive = this.cameraStream !== null;
        
        // Update selected camera
        this.selectedCameraId = this.cameraSelect.value;
        console.log('📹 Switching to camera:', this.selectedCameraId);
        
        // If camera was active, restart with new camera
        if (wasActive) {
            this.stopCamera();
            await this.startCamera();
        }
    }
    
    async enumerateMicrophones() {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.availableMicrophones = devices.filter(device => device.kind === 'audioinput');
            
            console.log('🎤 Available microphones:', this.availableMicrophones);
            
            // Populate microphone select
            this.microphoneSelect.innerHTML = '';
            
            // Add default option
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = 'Microfono predefinito';
            this.microphoneSelect.appendChild(defaultOption);
            
            if (this.availableMicrophones.length === 0) {
                console.warn('⚠️ No microphones found');
                return;
            }
            
            this.availableMicrophones.forEach((microphone, index) => {
                const option = document.createElement('option');
                option.value = microphone.deviceId;
                
                // Generate friendly name
                let label = microphone.label || `Microfono ${index + 1}`;
                
                // Try to detect microphone type
                if (label.toLowerCase().includes('built-in') || label.toLowerCase().includes('internal')) {
                    label += ' 🎙️ (Integrato)';
                } else if (label.toLowerCase().includes('usb') || label.toLowerCase().includes('external')) {
                    label += ' 🎧 (Esterno)';
                } else if (label.toLowerCase().includes('bluetooth')) {
                    label += ' 📡 (Bluetooth)';
                } else if (label.toLowerCase().includes('headset') || label.toLowerCase().includes('headphone')) {
                    label += ' 🎧 (Cuffie)';
                }
                
                option.textContent = label;
                this.microphoneSelect.appendChild(option);
            });
            
            // Use default microphone (no specific selection)
            this.selectedMicrophoneId = null;
            
        } catch (error) {
            console.error('Error enumerating microphones:', error);
            this.microphoneSelect.innerHTML = '<option value="">Errore rilevamento microfoni</option>';
        }
    }
    
    switchMicrophone() {
        // Update selected microphone
        this.selectedMicrophoneId = this.microphoneSelect.value || null;
        console.log('🎤 Microphone selected:', this.selectedMicrophoneId || 'default');
        
        // Show confirmation
        const micName = this.microphoneSelect.options[this.microphoneSelect.selectedIndex].text;
        this.showToast(`Microfono selezionato: ${micName}`, 'info');
    }
    
    capturePhoto() {
        if (!this.cameraStream) return;
        
        const canvas = this.captureCanvas;
        const video = this.cameraFeed;
        
        // Set canvas dimensions to match video
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        
        // Draw video frame to canvas
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);
        
        // Get image data
        this.capturedImageData = canvas.toDataURL('image/jpeg', 0.8);
        
        // Show preview
        this.capturedImage.src = this.capturedImageData;
        this.imagePreview.style.display = 'block';
        this.sendImageBtn.style.display = 'inline-block';
        
        this.showToast('📸 Foto catturata! Premi SPAZIO per confermare o R per rifare', 'info');
    }
    
    retakePhoto() {
        this.imagePreview.style.display = 'none';
        this.sendImageBtn.style.display = 'none';
        this.capturedImageData = null;
    }
    
    confirmImage() {
        if (this.capturedImageData) {
            this.sendImageWithMessage('Analizza questa immagine');
        }
    }
    
    async sendImageWithMessage(message = '') {
        if (!this.capturedImageData) {
            this.showToast('Nessuna immagine catturata', 'warning');
            return;
        }
        
        const messageText = message || this.messageInput.value.trim() || 'Analizza immagine';
        await this.sendMessage(messageText, this.capturedImageData);
        
        // Clear image after sending
        this.retakePhoto();
    }
    
    async sendMessage(messageText = null, imageData = null) {
        const message = messageText || this.messageInput.value.trim();
        
        if (!message && !imageData) {
            this.showToast('Inserisci un messaggio o scatta una foto', 'warning');
            return;
        }
        
        if (!this.isSessionActive) {
            this.showToast('Sessione non attiva', 'error');
            return;
        }
        
        // Add user message to chat
        this.addUserMessage(message, imageData ? true : false);
        
        // Clear input
        this.messageInput.value = '';
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            // Prepare request body with voice timing
            const requestBody = {
                message: message,
                image_data: imageData
            };
            
            // ⏱️ Add voice timing if recording was used
            if (this.voiceRecordingStartTime && this.voiceRecordingEndTime) {
                requestBody.voice_recording_start = this.voiceRecordingStartTime;
                requestBody.voice_recording_end = this.voiceRecordingEndTime;
                console.log('⏱️ Sending voice timing:', {
                    start: this.voiceRecordingStartTime,
                    end: this.voiceRecordingEndTime,
                    duration: (this.voiceRecordingEndTime - this.voiceRecordingStartTime).toFixed(2) + 's'
                });
                
                // ⚠️ DON'T reset here - we need these values for audio timing update later!
                // They will be reset in sendAudioTimingMetrics() after audio playback ends
            }
            
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.addAssistantMessage(data.response);
                
                // Play voice response if enabled
                if (this.voiceOutputEnabled && data.response.message) {
                    // For multiple objects, include the full response plus navigation instructions
                    let textToRead = data.response.message;
                    
                    if (data.response.special_content && 
                        data.response.special_content.type === 'multiple_objects') {
                        const count = data.response.special_content.images.length;
                        // Include the actual response text, then add navigation instructions
                        textToRead = `${data.response.message}. Usa le frecce per spostarti tra i ${count} oggetti mostrati.`;
                    }
                    
                    await this.playVoiceResponse(textToRead);
                }
            } else {
                this.addErrorMessage(data.error || 'Errore nel processamento del messaggio');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.addErrorMessage('Errore di connessione');
        } finally {
            this.hideTypingIndicator();
        }
    }
    
    addUserMessage(message, hasImage = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        let imageHTML = '';
        if (hasImage) {
            imageHTML = '<div class="mb-2"><i class="fas fa-image me-1"></i><small>Immagine allegata</small></div>';
        }
        
        messageDiv.innerHTML = `
            <div class="message-content">
                ${imageHTML}
                ${message}
                <div class="message-timestamp">${this.formatTimestamp(new Date())}</div>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addAssistantMessage(response) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message';
        
        // 🧠 Check if response uses memory context
        let memoryBadge = '';
        if (response.message && (
            response.message.toLowerCase().includes('come ti ho detto') ||
            response.message.toLowerCase().includes('ricordi che') ||
            response.message.toLowerCase().includes('abbiamo già parlato') ||
            response.message.toLowerCase().includes('come abbiamo visto')
        )) {
            memoryBadge = '<span class="badge bg-primary me-2" title="Risposta basata sulla memoria conversazionale"><i class="fas fa-brain me-1"></i>Memoria</span>';
        }
        
        let specialContentHTML = '';
        if (response.special_content) {
            // Handle multiple objects (carousel)
            if (response.special_content.type === 'multiple_objects') {
                const images = response.special_content.images;
                const carouselId = 'carousel-' + Date.now();
                
                let carouselItems = images.map((img, index) => `
                    <div class="carousel-item ${index === 0 ? 'active' : ''}">
                        <div class="object-image-container">
                            <div class="alert alert-info mb-2">
                                <i class="fas fa-cube me-2"></i>
                                <strong>Oggetto ${index + 1} di ${images.length}:</strong> ${img.description}
                            </div>
                            <img src="data:image/jpeg;base64,${img.image_data}" 
                                 class="object-image d-block w-100 img-fluid rounded shadow-sm" 
                                 alt="${img.object_name}"
                                 onclick="this.classList.toggle('enlarged')">
                            <div class="mt-2 text-center">
                                <small class="text-muted">${img.object_name}</small>
                            </div>
                        </div>
                    </div>
                `).join('');
                
                let carouselIndicators = images.map((_, index) => `
                    <button type="button" 
                            data-bs-target="#${carouselId}" 
                            data-bs-slide-to="${index}" 
                            ${index === 0 ? 'class="active" aria-current="true"' : ''} 
                            aria-label="Oggetto ${index + 1}">
                    </button>
                `).join('');
                
                specialContentHTML = `
                    <div class="mb-3">
                        <div id="${carouselId}" class="carousel slide" data-bs-ride="false">
                            <div class="carousel-indicators">
                                ${carouselIndicators}
                            </div>
                            <div class="carousel-inner">
                                ${carouselItems}
                            </div>
                            <button class="carousel-control-prev" type="button" data-bs-target="#${carouselId}" data-bs-slide="prev">
                                <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                                <span class="visually-hidden">Precedente</span>
                            </button>
                            <button class="carousel-control-next" type="button" data-bs-target="#${carouselId}" data-bs-slide="next">
                                <span class="carousel-control-next-icon" aria-hidden="true"></span>
                                <span class="visually-hidden">Successivo</span>
                            </button>
                        </div>
                        <div class="text-center mt-2">
                            <small class="text-muted">
                                <i class="fas fa-hand-pointer me-1"></i>
                                Usa le frecce per navigare tra gli oggetti
                            </small>
                        </div>
                    </div>
                `;
            }
            // Handle single object image (inserireoggetto)
            else if (response.special_content.type === 'object_image') {
                specialContentHTML = `
                    <div class="mb-3 object-image-container">
                        <div class="alert alert-info mb-2">
                            <i class="fas fa-cube me-2"></i>
                            <strong>Oggetto da Inserire:</strong>
                        </div>
                        <img src="data:image/jpeg;base64,${response.special_content.image_data}" 
                             class="object-image img-fluid rounded shadow-sm" 
                             alt="Immagine dell'oggetto"
                             onclick="this.classList.toggle('enlarged')">
                        <div class="mt-2 text-center">
                            <small class="text-muted">
                                <i class="fas fa-hand-pointer me-1"></i>
                                Clicca sull'immagine per ingrandirla
                            </small>
                        </div>
                    </div>
                `;
            }
            // Handle completion image (lavorofinito, spedizione)
            else if (response.special_content.type === 'completion_image') {
                specialContentHTML = `
                    <div class="mb-3 completion-image-container">
                        <div class="alert alert-success mb-2">
                            <i class="fas fa-check-circle me-2"></i>
                            <strong>Riferimento Assemblaggio:</strong>
                        </div>
                        <img src="data:image/jpeg;base64,${response.special_content.image_data}" 
                             class="completion-image img-fluid rounded shadow-sm" 
                             alt="Immagine di completamento"
                             onclick="this.classList.toggle('enlarged')">
                        <div class="mt-2 text-center">
                            <small class="text-muted">
                                <i class="fas fa-info-circle me-1"></i>
                                ${response.special_content.message}
                            </small>
                        </div>
                    </div>
                `;
            }
        }
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <i class="fas fa-robot me-2"></i>
                ${memoryBadge}
                ${specialContentHTML}
                ${response.message}
                <div class="message-timestamp">${this.formatTimestamp(new Date(response.timestamp))}</div>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addSystemMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system-message';
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <i class="fas fa-info-circle me-2"></i>
                ${message}
                <div class="message-timestamp">${this.formatTimestamp(new Date())}</div>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addErrorMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message error-message';
        
        messageDiv.innerHTML = `
            <div class="message-content">
                <i class="fas fa-exclamation-triangle me-2"></i>
                ${message}
                <div class="message-timestamp">${this.formatTimestamp(new Date())}</div>
            </div>
        `;
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    showTypingIndicator() {
        this.hideTypingIndicator(); // Remove any existing indicator
        
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message typing-indicator-message';
        typingDiv.id = 'typingIndicator';
        
        typingDiv.innerHTML = `
            <div class="typing-indicator">
                <i class="fas fa-robot me-2"></i>
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        this.chatMessages.appendChild(typingDiv);
        this.scrollToBottom();
    }
    
    hideTypingIndicator() {
        const typingDiv = document.getElementById('typingIndicator');
        if (typingDiv) {
            typingDiv.remove();
        }
    }
    
    updateCameraStatus(message, type = 'info') {
        const icon = type === 'error' ? 'fa-exclamation-triangle' : 'fa-video-slash';
        this.cameraStatus.innerHTML = `
            <i class="fas ${icon} fa-3x mb-2"></i>
            <p>${message}</p>
        `;
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    formatTimestamp(date) {
        return date.toLocaleTimeString('it-IT', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    showLoading(show) {
        this.loadingOverlay.style.display = show ? 'flex' : 'none';
    }
    
    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.querySelector('.toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }
        
        // Create toast
        const toastId = 'toast-' + Date.now();
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger',
            'warning': 'bg-warning',
            'info': 'bg-info'
        }[type] || 'bg-info';
        
        const toastHTML = `
            <div id="${toastId}" class="toast show" role="alert">
                <div class="toast-header ${bgClass} text-white">
                    <i class="fas fa-bell me-2"></i>
                    <strong class="me-auto">DIA</strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            const toast = document.getElementById(toastId);
            if (toast) {
                toast.remove();
            }
        }, 5000);
    }
    
    showSessionStats(stats) {
        const statsMessage = `
            <strong>Statistiche Sessione:</strong><br>
            • Interazioni totali: ${stats.total_interactions}<br>
            • Immagini catturate: ${stats.images_captured || 0}<br>
            • Tempo medio risposta: ${(stats.avg_response_time || 0).toFixed(2)}s
        `;
        
        this.addSystemMessage(statsMessage);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.diaInterface = new DIAWebInterface();
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (window.diaInterface && window.diaInterface.cameraStream) {
        window.diaInterface.stopCamera();
    }
});
