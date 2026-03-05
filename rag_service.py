"""
RAG Service for DIA (Digital Intelligent Assistant)
Handles Retrieval-Augmented Generation operations
"""
import io
import os
import re
import fitz  # PyMuPDF
import uuid
import base64
import json
from PIL import Image
from typing import List, Dict, Any, Tuple

# Prevent ChromaDB from loading default embedding function at import time
os.environ['ANONYMIZED_TELEMETRY'] = 'False'

from langchain.retrievers.multi_vector import MultiVectorRetriever
from langchain.storage import InMemoryStore
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import chromadb
from chromadb.config import Settings
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from config import PDF_PATHS, CHROMA_COLLECTION_NAME, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_USE_JSON_MODE


class RAGService:
    """Service for handling RAG operations and document processing"""
    
    def __init__(self):
        self.vectorstore = None
        self.retriever = None
        self.model = None
        self.chain = None
        self.formatted_texts = ""
        self.images_64 = []
        self.image_summaries_64 = []
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize RAG components"""
        # Extract content from PDFs
        self.formatted_texts = self._extract_text_from_pdfs(PDF_PATHS)
        self.images_64, self.image_summaries_64 = self._extract_images_from_pdfs(PDF_PATHS)
        
        # Create vector store and retriever
        self._create_vector_store()
        self._create_model()
    
    def _extract_text_from_pdfs(self, pdf_paths: List[str]) -> str:
        """Extract text from multiple PDF files and combine them"""
        combined_text = ""
        
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                print(f"⚠️ PDF not found: {pdf_path}")
                continue
                
            doc = fitz.open(pdf_path)
            for page in doc:
                combined_text += page.get_text() + "\n\n"
            doc.close()
        
        return combined_text
    
    def _extract_images_from_pdfs(self, pdf_paths: List[str]) -> Tuple[List[str], List[str]]:
        """Extract images from PDFs and convert them to base64"""
        images_b64 = []
        image_descriptions = []
        
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                continue
                
            doc = fitz.open(pdf_path)
            for page_num, page in enumerate(doc):
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Convert to PIL Image
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Convert to base64
                    buffered = io.BytesIO()
                    image.save(buffered, format="JPEG")
                    img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    
                    images_b64.append(img_b64)
                    image_descriptions.append(f"Immagine dalla pagina {page_num+1} del manuale")
            
            doc.close()
        
        return images_b64, image_descriptions
    
    def _create_multi_vector_retriever(self, vectorstore, image_summaries, images, text_summaries, texts):
        """Create retriever that indexes summaries, but returns raw images or texts"""
        store = InMemoryStore()
        id_key = "doc_id"
        
        retriever = MultiVectorRetriever(
            vectorstore=vectorstore,
            docstore=store,
            id_key=id_key,
        )
        
        def add_documents(retriever, doc_summaries, doc_contents):
            doc_ids = [str(uuid.uuid4()) for _ in doc_contents]
            summary_docs = [
                Document(page_content=s, metadata={id_key: doc_ids[i]})
                for i, s in enumerate(doc_summaries)
            ]
            retriever.vectorstore.add_documents(summary_docs)
            retriever.docstore.mset(list(zip(doc_ids, doc_contents)))
        
        # Add text documents
        add_documents(retriever, text_summaries, texts)
        
        # Add image documents
        add_documents(retriever, image_summaries, images)
        
        return retriever
    
    def _create_vector_store(self):
        """Create and populate the vector store"""
        # Configure ChromaDB to avoid loading default embedding function
        chroma_settings = Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        
        self.vectorstore = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=OpenAIEmbeddings(),
            client_settings=chroma_settings
        )
        
        # Prepare data for retriever
        testo = [self.formatted_texts]
        sommario = ["Manuale di assemblaggio del Calendario dell'Avvento Unicorni Rosa"]
        
        # Create retriever
        self.retriever = self._create_multi_vector_retriever(
            self.vectorstore,
            self.image_summaries_64,
            self.images_64,
            sommario,
            testo
        )
    
    def _create_model(self):
        """Create the language model"""
        try:
            # Configurazione base
            model_kwargs = {
                "temperature": LLM_TEMPERATURE,
                "model": LLM_MODEL,
                "max_tokens": LLM_MAX_TOKENS
            }
            
            # Aggiungi JSON mode se abilitato
            if LLM_USE_JSON_MODE:
                print("✅ JSON Mode abilitato - Il modello restituirà sempre JSON valido")
                model_kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
            
            self.model = ChatOpenAI(**model_kwargs)
            
        except Exception as e:
            # Fallback with minimal parameters if there are compatibility issues
            print(f"⚠️ Errore nella creazione del modello standard: {e}")
            print("Tentativo con configurazione minima...")
            self.model = ChatOpenAI(
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE
            )
    
    def elenca_cartelle(self, percorso_cartella: str) -> str:
        """List folders in a directory"""
        if not os.path.exists(percorso_cartella):
            return f"La cartella {percorso_cartella} non esiste."
        
        if not os.path.isdir(percorso_cartella):
            return f"{percorso_cartella} non è una cartella."
        
        elementi = os.listdir(percorso_cartella)
        sottocartelle = []
        
        for elemento in elementi:
            percorso_completo = os.path.join(percorso_cartella, elemento)
            if os.path.isdir(percorso_completo):
                sottocartelle.append(elemento)
        
        if sottocartelle:
            return ", ".join(sottocartelle)
        else:
            return f"La cartella {percorso_cartella} non contiene sottocartelle."
    
    def encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode('utf-8')
    
    def looks_like_base64(self, sb: str) -> bool:
        """Check if the string looks like base64"""
        return re.match("^[A-Za-z0-9+/]+[=]{0,2}$", sb) is not None
    
    def is_image_data(self, b64data: str) -> bool:
        """Check if the base64 data is an image by looking at the start of the data"""
        image_signatures = {
            b"\xff\xd8\xff": "jpg",
            b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a": "png",
            b"\x47\x49\x46\x38": "gif",
            b"\x52\x49\x46\x46": "webp",
        }
        try:
            header = base64.b64decode(b64data)[:8]
            for sig, format in image_signatures.items():
                if header.startswith(sig):
                    return True
            return False
        except Exception:
            return False
    
    def resize_base64_image(self, base64_string: str, size: Tuple[int, int] = (128, 128)) -> str:
        """Resize an image encoded as a Base64 string"""
        img_data = base64.b64decode(base64_string)
        img = Image.open(io.BytesIO(img_data))
        
        resized_img = img.resize(size, Image.LANCZOS)
        
        buffered = io.BytesIO()
        resized_img.save(buffered, format=img.format)
        
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    def split_image_text_types(self, docs: List[Any]) -> Dict[str, List[str]]:
        """Split base64-encoded images and texts"""
        b64_images = []
        texts = []
        
        for doc in docs:
            if isinstance(doc, Document):
                doc = doc.page_content
            if self.looks_like_base64(doc) and self.is_image_data(doc):
                doc = self.resize_base64_image(doc, size=(1300, 600))
                b64_images.append(doc)
            else:
                texts.append(doc)
        
        return {"images": b64_images, "texts": texts}
    
    def split_image(self, image_path: str) -> Dict[str, str]:
        """Split image for processing"""
        return {"img": image_path}
    
    def get_split_param(self) -> str:
        """Get the current image path if it exists"""
        if os.path.exists("captured_image.jpg"):
            return "captured_image.jpg"
        return ""
    
    def img_prompt_func(self, data_dict: Dict[str, Any], job_number: str, memory_context: str = "") -> List[HumanMessage]:
        """Create prompt with context for the LLM"""
        messages = []
        
        # Add image if available
        if data_dict["context"]["img"]:
            with open(data_dict["context"]["img"], "rb") as image_file:
                image_message = {
                    "type": "image_url",
                    "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(image_file.read()).decode()}
                }
                messages.append(image_message)
        
        # Get list of available objects
        lista = self.elenca_cartelle("content/images")
        
        # 🧠 Prepara sezione memoria se disponibile
        memory_section = ""
        if memory_context:
            memory_section = f"\n\n🧠 MEMORIA CONVERSAZIONALE:\n{memory_context}\n\nUSA QUESTE INFORMAZIONI per fornire risposte più contestuali. Se l'utente chiede informazioni su un oggetto o box già discusso, fai riferimento alle interazioni precedenti. Ad esempio: 'Come ti ho detto prima...' o 'Ricordi che abbiamo parlato di...'\n"
        
        # Create the main text prompt
        text_message = {
            "type": "text",
            "text": (
                "Sei un chatbot che aiuta gli utenti durante il processo di assemblaggio di una scatola, definita job.\n"
                "Sei in grado sia di fornire supporto solo testuale ma puoi anche analizzare un'immagine per fornire ulteriore supporto.\n"
                f"Ogni utente dovrà assemblare un job {str(job_number)}. Ora devi fare riferimento solamente al JOB {str(job_number)}, che sarebbe la versione {str(job_number)}. Non dare informazioni sull'altra versione.\n"
                f"{memory_section}"
                "Il job in questione è un calendario dell'avvento composto da 24 box colorate di dimensioni differenti e numerate rispettivamente da 1 a 24 con un numero bianco posizionato sulla faccia principale.\n"
                "In ogni box deve essere inserito uno e un solo oggetto definito item secondo le informazioni del tuo contesto.\n"
                "Quando ti viene chiesto se un item va in una specifica box tu devi sempre dire se quell'item va in quella box o in un'altra.\n"
                "Una volta che ti viene mostrato un oggetto che è già stato inserito dai informazioni su quell'oggetto ma specifica che è già stato inserito.\n"
                "Spesso ti sarà richiesto di analizzare direttamente l'immagine dell'item da inserire in una box. Basati sulle immagini nel tuo contesto per rispondere.\n"
                "IMPORTANTE ANALISI IMMAGINI: Quando analizzi un'immagine catturata, devi determinare:\n"
                "  - Se è un OGGETTO: identificalo usando il mapping degli oggetti disponibili, comunica quale oggetto è e in quale box deve essere inserito. Usa la chiave 'usarescatola'. NON VERRÀ MOSTRATA ALCUNA IMMAGINE all'utente, solo la tua risposta testuale.\n"
                "  - Se è una BOX: leggi il numero sulla box e comunica quale oggetto deve essere inserito in quella box. Usa la chiave 'inserireoggetto' con il formato 'descrizione;__nomeoggetto'. L'IMMAGINE DELL'OGGETTO VERRÀ MOSTRATA all'utente.\n"
                "  - Se ci sono MULTIPLE BOX nell'immagine: analizza TUTTE le box presenti, leggi il numero su CIASCUNA e fornisci le informazioni per TUTTE separate da '||'. Esempio: 'Box 1: descrizione;__oggetto1||Box 5: descrizione;__oggetto5||Box 12: descrizione;__oggetto12'. LE IMMAGINI DEGLI OGGETTI VERRANNO MOSTRATE.\n"
                "  - Se ci sono MULTIPLE OGGETTI nell'immagine: analizza TUTTI gli oggetti presenti, identificali e indica per CIASCUNO in quale box va inserito, separando le risposte con '||'. NON VERRANNO MOSTRATE IMMAGINI, solo la tua risposta testuale.\n"
                "ATTENZIONE: Non limitarti al primo elemento visibile nell'immagine. Scansiona l'intera immagine per identificare TUTTI gli oggetti o box presenti.\n"
                "Se un'immagine ti sembra poco chiara, chiedi all'utente di fornire anche una descrizione vocale così da fornirti maggiori informazioni.\n"
                "Alcuni item sono difettosi. Il difetto è rappresentato da un bollino rosso apposto sull'oggetto. Ogni volta che analizzi l'immagine di un item, verifica se è presente il bollino. In caso affermativo comunica all'utente che è difettoso.\n"
                "Una volta che l'utente avrà inserito tutti gli item nelle 24 box, dovrà inserire le box nel job disponendoli in ordine corretto.\n"
                "L'utente ti potrà chiedere di confrontare il job assemblato da lui con la versione reale che doveva assemblare. Tu dovrai dirgli se il suo assemblaggio è corretto.\n"
                "Per verificare che l'assemlaggio sia corretto verifica con estrema precisione la disponsizione delle scatole.\n"
                "Usa sempre le informazioni del manuale per rispondere alle domande.\n"
                "Cerca di essere conciso ma estremamente preciso, evita di essere ridondante.\n"
                "\n"
                "⚠️ FORMATO RISPOSTA OBBLIGATORIO ⚠️\n"
                "Devi SEMPRE rispondere SOLO con un oggetto JSON valido nel formato: {\"chiave\": \"valore\"}\n"
                "NON aggiungere testo prima o dopo il JSON.\n"
                "NON usare markdown code blocks (```json).\n"
                "NON spiegare che stai usando JSON.\n"
                "SOLO il JSON puro: {\"chiave\": \"valore\"}\n"
                "\n"
                "La chiave può essere 'inserireoggetto' se data una scatola viene chiesto quale oggetto inserire, 'usarescatola' se dato un oggetto viene chiesto in quale scatola inserirlo, 'lavorofinito' se l'utente esprime il fatto che ha terminato la fase di inserimento degli oggetti nelle scatole e che ora deve inserirli nel calendario dell'avventoù, 'spedizione' quando l'utente esprime il fatto che ha posizionato tutte le scatole (box) all'interno del calendario dell'avvento e ora deve inserire l'etichetta per la spedizione o 'altro' per altri casi.\n"
                f"Il valore sarà la risposta effettiva alla domanda, se il valore si riferisce alla chiave 'inserireoggetto' o 'usarescatola' alla fine della risposta aggiungi ';__nomeoggetto' dove nomeoggetto è una stringa presa da questa lista di oggetti a cui corrisponde l'oggetto da inserire: {lista} \n"
                "\n"
                "IMPORTANTE - FORMATO PER RISPOSTE MULTIPLE:\n"
                "1. MULTIPLE BOX (chiave 'inserireoggetto'): Se l'utente chiede informazioni su più box contemporaneamente, devi rispondere con TUTTE le informazioni separate da '||'.\n"
                "   Formato: 'Box 9: descrizione oggetto;__nomeoggetto1||Box 14: descrizione oggetto;__nomeoggetto2||Box 16: descrizione oggetto;__nomeoggetto3'\n"
                "   Esempio: 'Box 1: unicorno rosa;__unicorno rosa||Box 2: anello blu;__anello blu con arcobaleno||Box 3: bracciale;__bracciale arcobaleno'\n"
                "\n"
                "2. MULTIPLE OGGETTI (chiave 'usarescatola'): Se nell'immagine ci sono più oggetti, devi identificare CIASCUN oggetto e indicare in quale box va inserito, separando le risposte con '||'.\n"
                "   Formato: 'Oggetto 1 (nome): va nella box X;__nomeoggetto1||Oggetto 2 (nome): va nella box Y;__nomeoggetto2||Oggetto 3 (nome): va nella box Z;__nomeoggetto3'\n"
                "   Esempio: 'Unicorno rosa: va nella box 1;__unicorno rosa||Anello blu con arcobaleno: va nella box 2;__anello blu con arcobaleno||Bracciale arcobaleno: va nella box 3;__bracciale arcobaleno'\n"
                "   IMPORTANTE: Per ogni oggetto, specifica SEMPRE in quale box deve essere inserito E aggiungi ';__nomeoggetto' alla fine!\n"
                f"Domanda: {data_dict['question']}\n\n"
                "Testo e/o tabelle e/o liste:\n"
                f"{self.formatted_texts}"
            ),
        }
        
        messages.append(text_message)
        
        # Clear the image path after processing
        data_dict["context"]["img"] = None
        
        return [HumanMessage(content=messages)]
    
    def create_rag_chain(self, job_number: str):
        """Create the RAG chain"""
        self.job_number = job_number  # Store for later use
        chain = (
            {
                "context": self.retriever | RunnableLambda(lambda x: self.split_image(self.get_split_param())),
                "question": RunnablePassthrough(),
            }
            | RunnableLambda(lambda x: self.img_prompt_func(x, job_number, getattr(self, '_current_memory_context', '')))
            | self.model
            | StrOutputParser()
        )
        
        self.chain = chain
        return chain
    
    def invoke_chain(self, query: str, memory_context: str = "") -> str:
        """Invoke the RAG chain with a query and optional memory context"""
        if not self.chain:
            raise ValueError("RAG chain not initialized. Call create_rag_chain first.")
        
        # Store memory context temporarily for use in img_prompt_func
        self._current_memory_context = memory_context
        
        result = self.chain.invoke(query)
        
        # Clear memory context after use
        self._current_memory_context = ""
        
        return result


# Utility functions
def clean_markdown(text: str) -> Tuple[str, str]:
    """Clean markdown formatting and extract JSON values"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log della risposta originale per debug
    logger.info(f"📥 Risposta LLM ricevuta (primi 200 char): {text[:200]}...")
    
    try:
        # Prova a parsare direttamente come JSON
        json_obj = json.loads(text)
        
        # Print key and value separately
        for chiave, valore in json_obj.items():
            logger.info(f"✅ JSON parsato - Chiave: {chiave}, Valore: {valore[:100]}...")
            return chiave, valore
            
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ Errore parsing JSON diretto: {e}")
        
        # Tentativo 2: Rimuovi markdown code blocks se presenti
        cleaned_text = text.strip()
        
        # Rimuovi ```json e ``` se presenti
        if cleaned_text.startswith('```'):
            logger.info("🔧 Rilevato markdown code block, rimozione...")
            lines = cleaned_text.split('\n')
            # Rimuovi prima e ultima riga se sono marker markdown
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            cleaned_text = '\n'.join(lines).strip()
            logger.info(f"🔧 Testo pulito: {cleaned_text[:200]}...")
        
        try:
            json_obj = json.loads(cleaned_text)
            for chiave, valore in json_obj.items():
                logger.info(f"✅ JSON parsato dopo pulizia - Chiave: {chiave}")
                return chiave, valore
        except json.JSONDecodeError as e2:
            logger.warning(f"⚠️ Errore parsing JSON dopo pulizia: {e2}")
            
            # Tentativo 3: Cerca pattern JSON nel testo
            import re
            json_pattern = r'\{[^{}]*\}'
            matches = re.findall(json_pattern, cleaned_text)
            
            if matches:
                logger.info(f"🔍 Trovati {len(matches)} possibili JSON nel testo")
                for match in matches:
                    try:
                        json_obj = json.loads(match)
                        for chiave, valore in json_obj.items():
                            logger.info(f"✅ JSON estratto da pattern - Chiave: {chiave}")
                            return chiave, valore
                    except:
                        continue
            
            # Se tutto fallisce, logga l'errore completo e restituisci valori di default
            logger.error(f"❌ ERRORE PARSING JSON - Testo completo:\n{text}")
            logger.error(f"❌ Impossibile estrarre JSON valido dalla risposta")
            
            # Prova a restituire almeno il testo come risposta "altro"
            return "altro", text.strip() if text.strip() else "Errore nella risposta del sistema"


def get_rag_service() -> RAGService:
    """Get a RAGService instance"""
    return RAGService()
