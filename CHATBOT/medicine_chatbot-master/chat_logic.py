# Updated imports and environment variables
import os
import re 
from datetime import datetime
from typing import Optional, List, Any, Tuple
from bson.objectid import ObjectId
from pymongo import MongoClient, errors as mongo_errors

# --- LangChain & RAG Imports ---
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.schema import BaseRetriever, Document
from langchain.memory import ConversationBufferMemory
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer


# --- Setup: Database & Core Models ---
# Use environment variables with robust defaults for configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Initialize database connections
user_collection: Any = None
drug_collection: Any = None
client: Optional[MongoClient] = None
try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping') # Verify connection
    user_db = client["user_db"]
    user_collection = user_db["users"]
    drug_db = client["drugbank_db"]
    drug_collection = drug_db["drugs"]
    print("DEBUG: MongoDB connection successful.")
except Exception as e:
    print(f"FATAL: Failed to connect to MongoDB: {e}")

# 2. RAG Component Setup
llm: Optional[Ollama] = None
embedding_model: Optional[SentenceTransformer] = None
chroma_collection: Any = None 

try:
    llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
    
    # Initialize SentenceTransformer (using the name)
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Initialize ChromaDB client and collection
    CHROMA_PATH = os.getenv("CHROMA_PATH", "./chromadb")
    chroma_client = PersistentClient(path=CHROMA_PATH)
    chroma_collection = chroma_client.get_or_create_collection("drug_data")

    print("DEBUG: RAG components initialized successfully.")
except Exception as e:
    print(f"FATAL: Failed to initialize RAG components: {e}")

# --- PROMPT TEMPLATES (ADJUSTED FOR CONVERSATIONAL FLOW) ---

# 3. Primary RAG Prompt Template (ULTRA-ENFORCED)
prompt_template = PromptTemplate.from_template("""
You are a highly reliable, empathetic, and professional health assistant specializing in drug information and interactions. Your primary goal is to provide clear, concise, and helpful answers based on the context provided.

User's question: {question}

Conversation History:
{history}

User details:
{user_details}

--- KNOWLEDGE CONTEXT FOR ANSWERING THE QUESTION ---
{context}
--- END KNOWLEDGE CONTEXT ---

MANDATORY INSTRUCTION (Anti-Contradiction Rule):
1. If the KNOWLEDGE CONTEXT contains a section starting with **'!!! MANDATORY INTERACTION WARNING !!!'**, you **MUST** prioritize that information.
2. If a CRITICAL FINDING is present, **DO NOT** use cautious terms like "might" or "potential." Instead, translate the CRITICAL FINDING's severity and details **DIRECTLY** into your conversational response.
3. NEVER state "no interaction found" or similar if a CRITICAL FINDING is present.

Analyze the user's question, prioritize the CRITICAL FINDING, and answer clearly, professionally, and in a conversational style.

If the context does not contain the answer, say: "I cannot provide a specific answer based on the drug information available in my database, but I strongly recommend consulting a healthcare professional."
""")

# 4. General Chat Prompt Template (For non-drug-related questions)
GENERAL_PROMPT_TEMPLATE = PromptTemplate.from_template("""
You are a helpful, friendly, and professional health assistant. 
Answer the user's question based on your general knowledge. If the question is about a specific drug, interaction, or requires personalized medical advice, politely and clearly state that you can only answer with information from your verified database, and suggest they rephrase the query with a specific drug name.

Conversation History:
{history}

User's question: {question}

Response:
""")

# 5. User Detail Retrieval Prompt Template (NEW: To override safety guardrail)
USER_DETAIL_PROMPT_TEMPLATE = PromptTemplate.from_template("""
You are a reliable assistant with temporary access to a user's profile information. Your task is to directly and clearly answer the user's question using ONLY the provided 'User Profile Data' and 'Conversation History' below.

Conversation History:
{history}

--- User Profile Data ---
{user_details}
--- END User Profile Data ---

User's question: {question}

If the specific requested information (e.g., prescriptions, allergies) is **not present** in the 'User Profile Data', you must respond with: "The system does not currently list any [data_type] for your profile." (Replace [data_type] with the item they asked for, e.g., prescriptions).

Response:
""")

# --- Helper Classes & Functions ---

class ChromaDrugRetriever(BaseRetriever):
    """
    Custom Retriever for ChromaDB. Includes 'exclude_interactions' flag 
    to filter out documents related to drug-drug interactions.
    """
    model: SentenceTransformer
    collection: Any 
    drug_id: Optional[str] = None
    k: int = 5 
    exclude_interactions: bool = False # NEW FLAG

    def get_relevant_documents(self, query: str, **kwargs) -> list[Document]:
        if self.collection is None or self.model is None:
            print("RETRIEVER ERROR: Chroma collection or embedding model is not initialized.")
            return []
            
        where_filter = {}
        if self.drug_id:
            where_filter["drugbank_id"] = self.drug_id
            
        # CRITICAL FIX: Exclude interaction documents if flag is set (for general info queries)
        if self.exclude_interactions:
            # Assumes interaction chunks have a metadata field 'section' set to 'drug_interactions'
            if where_filter:
                 where_filter = {"$and": [where_filter, {"section": {"$ne": "drug_interactions"}}]}
            else:
                 where_filter = {"section": {"$ne": "drug_interactions"}}
            print(f"RETRIEVER DEBUG: Excluding interaction documents for {self.drug_id or 'all'}.")


        try:
            query_embedding = self.model.encode(query).tolist()
        except Exception as e:
            print(f"RETRIEVER ERROR: Failed to encode query: {e}")
            return []
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=self.k, 
                where=where_filter, 
                include=['documents', 'metadatas'] 
            )
        except Exception as e:
            print(f"RETRIEVER ERROR: Chroma query failed: {e}")
            return []
        
        documents_list = results.get("documents", [[]])[0]
        ids_list = results.get("ids", [[]])[0] 
        metadatas_list = results.get("metadatas", [[]])[0]

        if not documents_list:
            print(f"RETRIEVER DEBUG: No documents found for drug_id {self.drug_id or 'N/A'} and query with filter.")
            return []
        
        docs = [
            Document(
                page_content=doc_text, 
                metadata={**meta, "id": doc_id} 
            ) 
            for doc_text, doc_id, meta in zip(documents_list, ids_list, metadatas_list)
        ]
        return docs


def format_list(label: str, items: list) -> str:
    """Formats list fields (like allergies, prescriptions) for the prompt."""
    if not items:
        return ""
    if all(isinstance(i, dict) for i in items):
        # Use idx for index to avoid variable shadowing
        lines = [
            f"{label} {idx+1}: " + ", ".join(f"{k}: {v}" for k, v in item.items() if v)
            for idx, item in enumerate(items)
        ]
        return "\n".join(lines)
    else:
        return f"{label}: " + ", ".join(str(i) for i in items)


def get_user_details_text(user_data: dict) -> str:
    """Formats the user document into a string for the LLM prompt context."""
    if not user_data:
        # Crucial for the LLM to know if data is truly absent or just wasn't passed
        return "User details not found or minimal. No profile data available." 

    parts = []
    # Scalar fields
    scalar_fields = ["first_name", "last_name", "age", "gender", "height_cm", "weight_kg"]
    for field in scalar_fields:
        val = user_data.get(field)
        if val is not None:
            parts.append(f"{field.replace('_', ' ').title()}: {val}")

    # List/Dict fields
    list_fields = ["allergies", "family_history", "prescriptions", "surgeries"]
    for field in list_fields:
        val = user_data.get(field, [])
        formatted = format_list(field.replace('_', ' ').title(), val)
        if formatted:
            parts.append(formatted)

    if not parts:
         return "User profile exists, but contains no current health or personal details."
         
    return "\n".join(parts)


def find_drug_by_name(word: str) -> Optional[dict]:
    """Searches MongoDB for a drug matching the given name/synonym."""
    if drug_collection is None:
        print("MongoDB drug collection is not available.")
        return None
    
    # CRITICAL FIX: Escape special regex characters in the search word
    escaped_word = re.escape(word)

    try:
        # Complex query for robust drug searching
        result = drug_collection.find_one({
            "$or": [
                # Exact name match (case-insensitive)
                {"name": {"$regex": f"^{escaped_word}$", "$options": "i"}},
                # Product name contains the word (case-insensitive substring)
                {"products.name": {"$regex": escaped_word, "$options": "i"}},
                # Synonym contains the word (case-insensitive substring)
                {"synonyms": {"$elemMatch": {"$regex": escaped_word, "$options": "i"}}}
            ]
        })
        return result
    except mongo_errors.PyMongoError as e:
        print(f"MongoDB search error: {e}")
        return None


def extract_drug_from_text_ner(text: str, llm: Any) -> List[dict]:
    """
    Uses the LLM (Ollama) to perform Named Entity Recognition (NER)
    for drug names and validates them against MongoDB.
    
    Returns up to two distinct drug documents.
    """
    if llm is None:
        print("NER ERROR: LLM is not initialized.")
        return []
        
    ner_prompt = PromptTemplate.from_template("""
    Analyze the following user query. Your sole task is to extract the names of up to two distinct medications (drugs) mentioned.
    
    If you find drug names, return them as a comma-separated list, EXACTLY as they appear in the query (e.g., Aspirin, Tylenol).
    If you find only one, return just that name (e.g., Aspirin).
    If you find zero drugs, return the word: NONE
    
    Query: {query}
    
    Extracted Drug Names (comma-separated, or NONE):
    """)
    
    full_prompt = ner_prompt.format(query=text)

    try:
        # Use a short temperature/max_tokens for reliable, concise output
        response = llm.invoke(full_prompt, temperature=0.01, max_tokens=100).strip()
    except Exception as e:
        print(f"NER LLM execution error: {e}")
        return []

    if response.upper() == "NONE":
        print("NER DEBUG: LLM found no drugs in the query.")
        return []

    drug_names = [name.strip() for name in response.split(',') if name.strip()]
    
    found_drugs = []
    found_ids = set()

    for name in drug_names:
        # Validate the drug name against MongoDB to ensure it's a known entity
        result = find_drug_by_name(name)
        if result and result.get("drugbank_id") and result.get("drugbank_id") not in found_ids:
            found_drugs.append(result)
            found_ids.add(result.get("drugbank_id"))
            if len(found_drugs) >= 2:
                break
                
    print(f"NER DEBUG: LLM extracted: {drug_names}. Validated drugs: {[d.get('name') for d in found_drugs]}")
    return found_drugs


# Dictionary to hold conversation memory, keyed by user_id
session_memories = {}

def get_chat_memory(user_id: str):
    """Retrieves or creates a ConversationBufferMemory for the user."""
    # LangChainDeprecationWarning is handled by the user/system here
    if user_id not in session_memories:
        session_memories[user_id] = ConversationBufferMemory(memory_key="history", return_messages=False)
    return session_memories[user_id]

def reset_chat_history(user_id: str) -> bool:
    """Clears the chat history for a specific user ID."""
    if user_id in session_memories:
        del session_memories[user_id]
        print(f"DEBUG: Chat history cleared for user: {user_id}")
        return True
    return False

def _get_user_and_memory(user_id_str: Optional[str]) -> Tuple[str, dict, str, Any]:
    """Helper to fetch user data, set ID, and retrieve memory/history."""
    user_data = {}
    user_id = user_id_str or "default_user" 

    if user_id_str and user_collection is not None:
        try:
            if ObjectId.is_valid(user_id_str):
                user_data = user_collection.find_one({"_id": ObjectId(user_id_str)}) or {}
            else:
                user_data = user_collection.find_one({"_id": user_id_str}) or {}
                
            if not user_data:
                print(f"WARNING: User ID {user_id_str} not found in database.")
                
        except mongo_errors.PyMongoError as e:
            print(f"MongoDB user fetch error: {e}")
            
    user_details_text = get_user_details_text(user_data)
    chat_memory = get_chat_memory(user_id)
    history = chat_memory.buffer if hasattr(chat_memory, 'buffer') else ""
    
    return user_id, user_data, user_details_text, chat_memory

def _extract_drugs_and_check_history(question: str, history: str, llm: Any) -> List[dict]:
    """
    Extracts drugs from the current query using NER and falls back to history if zero drugs are found,
    or if the query is a very short follow-up (like 'those drugs').
    """
    # Check for short, vague follow-up questions
    vague_follow_up = bool(re.search(r'\b(those\s+drugs|the\s+drugs|it|them|side\s+effects|both)\b', question.lower()))
    
    # 1. Extract Drug(s) from current question - NOW USING NER
    mongo_matches = extract_drug_from_text_ner(question, llm)
    
    # 2. History-Aware Drug Fallback: If current extraction found nothing OR it's a vague follow-up.
    if not mongo_matches or (vague_follow_up and len(mongo_matches) < 2):
        print("DEBUG: Current extraction found few drugs or is vague. Checking chat history for prior drug IDs...")
        
        # --- CRITICAL FIX 1: Simplify and Sanitize History for Robust Extraction ---
        # Strip excess formatting and the 'User: ' / 'AI: ' prefixes to stabilize regex on citation block.
        sanitized_history = history.replace('*', '').replace('\n', ' ').replace('\r', ' ')
        sanitized_history = sanitized_history.replace('AI: ', '').replace('User: ', '') 
        
        # 2. Use a robust regex to find the last-mentioned DrugBank IDs (DB####) and associated names.
        citation_matches = re.findall(r'(Primary Drug|Secondary Drug):\s*(.*?)\s*\(ID:\s*(DB\d+)\)', sanitized_history)
        
        history_matches = []
        history_ids = set()
        
        # 3. Process matches backward to find the latest two distinct IDs.
        for match_type, name, db_id in reversed(citation_matches):
            if db_id not in history_ids:
                # Use find_one to get the full drug document for context passing
                doc = drug_collection.find_one({"drugbank_id": db_id})
                if doc:
                    # Prepend to history_matches to maintain the original citation order (Primary then Secondary)
                    history_matches.insert(0, doc) 
                    history_ids.add(db_id)
                    if len(history_matches) >= 2:
                        break

        if history_matches:
            print(f"DEBUG: Prioritizing {len(history_matches)} drug(s) context from chat history.")
            return history_matches
    
    # If history fallback fails or is not needed, use current matches
    return mongo_matches

# Assuming find_drug_by_name and all other dependencies are available
def _check_interactions(primary_match: dict, secondary_drugs_to_check: List[dict]) -> Tuple[str, List[str], Optional[dict]]:
    """
    Checks for structured interactions (from MongoDB's drug_interactions field) 
    and returns critical context and sources.
    
    Returns: (interaction_context, sources_list, secondary_for_rag)
    """
    direct_interaction_context = ""
    sources_list = []
    secondary_for_rag = None 
    
    primary_interactions = primary_match.get("drug_interactions", [])
    primary_name = primary_match.get("name", 'N/A')
    primary_id = primary_match.get("drugbank_id", 'N/A')
    
    # Iterate through all secondary drugs compiled by _get_secondary_drugs_for_check
    for secondary_drug in secondary_drugs_to_check:
        secondary_drugbank_id = secondary_drug.get("drugbank_id")
        secondary_name = secondary_drug.get("name", 'N/A')
        
        # 1. Structured Interaction Check (Prioritize and return immediately)
        for interaction in primary_interactions:
            # Check if the interaction document matches the secondary drug's ID
            if interaction.get("drugbank_id") == secondary_drugbank_id:
                # *** CRITICAL INTERACTION FOUND - USE AGGRESSIVE FORMATTING ***
                description = interaction.get('description', 'NO DESCRIPTION: Interaction is marked but details are missing.')
                direct_interaction_context += (
                    f"!!! MANDATORY INTERACTION WARNING !!!\n" 
                    f"--- CRITICAL FINDING: DIRECT DRUG INTERACTION IDENTIFIED ---\n"
                    f"*** PRIMARY INTERACTOR ***: **{primary_name}** (ID: {primary_id})\n"
                    f"*** SECONDARY INTERACTOR ***: **{secondary_name}** (ID: {secondary_drugbank_id})\n"
                    f"*** CLINICAL SIGNIFICANCE & DETAILS ***:\n" 
                    f"{description}\n"
                    f"--- END CRITICAL FINDING ---\n\n"
                )
                sources_list.append(f"Structured Interaction Data for {primary_name} vs {secondary_name}")
                secondary_for_rag = secondary_drug
                print(f"DIRECT INTERACTION DEBUG: Found structured interaction between {primary_name} and {secondary_name}.")
                
                # If a direct interaction is found, return immediately.
                return direct_interaction_context, sources_list, secondary_for_rag

        # If no structured interaction was found for the current secondary drug, 
        # but this is the first drug found, set it for RAG context building.
        if secondary_for_rag is None:
             secondary_for_rag = secondary_drug
    
    # If the loop completes without finding a direct interaction, 
    # secondary_for_rag will hold the last checked secondary drug (if any).
    return direct_interaction_context, sources_list, secondary_for_rag

def _get_secondary_drugs_for_check(query_matches: List[dict], primary_match: dict, user_data: dict) -> List[dict]:
    """Compiles a list of unique secondary drugs (from query and prescriptions) to check against the primary drug."""
    
    primary_id = primary_match.get("drugbank_id")
    secondary_drugs_to_check = []
    
    checked_ids = {primary_id}
    
    # 1. Secondary Drug from query (if found, index 1)
    if len(query_matches) > 1:
        secondary_doc = query_matches[1]
        secondary_id = secondary_doc.get("drugbank_id")
        if secondary_id and secondary_id not in checked_ids:
            secondary_drugs_to_check.append(secondary_doc)
            checked_ids.add(secondary_id)
            print(f"DEBUG: Added secondary drug from query: {secondary_doc.get('name')}")
    
    # 2. Drugs from user's prescriptions
    if user_data:
        prescribed_items = user_data.get("prescriptions", [])
        
        for p_item in prescribed_items:
            p_name = p_item.get('drug') if isinstance(p_item, dict) else str(p_item)
            
            if p_name:
                prescribed_doc = find_drug_by_name(p_name)
                
                if prescribed_doc:
                    prescribed_id = prescribed_doc.get("drugbank_id")
                    
                    if prescribed_id and prescribed_id not in checked_ids:
                        secondary_drugs_to_check.append(prescribed_doc)
                        checked_ids.add(prescribed_id)
                        print(f"DEBUG: Added secondary drug from prescriptions: {prescribed_doc.get('name')}")
    
    return secondary_drugs_to_check

from typing import Literal

# This constant is a simple prompt template specifically for intent classification.
# It should be defined outside the function, similar to your other prompt templates.
INTENT_CLASSIFICATION_PROMPT = """
You are an intent classification system for a medical chatbot. Your task is to analyze the user's question and classify its primary intent.

**CRITICAL INSTRUCTION:** You MUST respond with ONLY ONE of the following classification labels. Do not include any other text, explanation, or punctuation.

**Labels:**
1. **INTERACTION:** The user is asking about an interaction, combining, or co-administration of a drug with another drug, food, or condition (e.g., "What is the interaction of X and Y?", "Can I take X with a meal?", "Is it safe to take X with my heart condition?").
2. **GENERAL_INFO:** The user is asking for facts, uses, mechanism, side effects, dosage, or general description of a single drug (e.g., "What is X used for?", "Tell me about drug X.", "What are the side effects of X?").
3. **OTHER:** The question is general, administrative, or out of scope (e.g., "Thank you", "Reset history", "What are my prescriptions?").

Question to classify: "{question}"

Intent: 
"""

def _classify_rag_intent(question: str, llm) -> Literal["INTERACTION", "GENERAL_INFO", "OTHER"]:
    """
    Uses the LLM to classify the user's intent for a single-drug query 
    to determine if interaction documents should be excluded from RAG.
    """
    
    # Check for obvious flags first to save an LLM call if possible
    # This is an optional optimization but improves speed and reduces LLM cost
    interaction_keywords = ["interact", "combine", "take with", "together", "contraindicated", "safe with"]
    if any(keyword in question.lower() for keyword in interaction_keywords):
        return "INTERACTION"

    # Use a low-temperature call to force a precise, non-creative response
    try:
        # Note: You may need to use a specific LLM invocation method if your 
        # llm object does not directly support low temperature or structured output,
        # but for simple classification, invoking with a strict prompt often works.
        
        # We assume the llm is a LangChain-style runnable
        response = llm.invoke(INTENT_CLASSIFICATION_PROMPT.format(question=question)).strip().upper()
        
        if "INTERACTION" in response:
            return "INTERACTION"
        if "GENERAL_INFO" in response:
            return "GENERAL_INFO"
        
        return "OTHER" # Default to 'OTHER' if the classification fails or is ambiguous
        
    except Exception as e:
        print(f"Intent classification LLM error: {e}. Defaulting to GENERAL_INFO.")
        # Defaulting to GENERAL_INFO for safety: better to retrieve less context than too much.
        return "GENERAL_INFO"
def _get_drug_context_rag_docs(drug_doc: dict, question: str, exclude_interactions: bool = False) -> Tuple[List[Document], str]:
    """
    Runs RAG for a single drug, using the exclude_interactions flag for filtering, 
    and returns documents and contextual header.
    """
    drug_id = drug_doc.get("drugbank_id")
    drug_name = drug_doc.get("name", 'N/A')
    
    if not drug_id or not embedding_model or not chroma_collection:
        print(f"RAG DEBUG: Skipping RAG for {drug_name}. Missing ID or components.")
        return [], ""
        
    # CRITICAL FIX: Initialize retriever with the exclusion flag
    retriever = ChromaDrugRetriever(
        model=embedding_model, 
        collection=chroma_collection, 
        drug_id=drug_id,
        exclude_interactions=exclude_interactions 
    )
    
    docs = retriever.get_relevant_documents(question)
    
    if docs:
        header = f"\n--- DRUG CONTEXT: {drug_name} (ID: {drug_id}) ---\n"
        context = "\n---\n".join(doc.page_content for doc in docs)
        footer = f"\n--- END DRUG CONTEXT: {drug_name} ---\n"
        return docs, header + context + footer
    
    return [], ""


def handle_chat_query(question: str, user_id_str: Optional[str]) -> tuple[str, int]:
    """Core logic for the RAG-powered chat query."""
    
    # 1. Initialization Check
    if llm is None or embedding_model is None or chroma_collection is None or drug_collection is None:
        return "Chat system is currently unavailable due to failed initialization of LLM/DB components. Please check server logs.", 500

    # 2. History Reset Check
    if question.lower().strip() == "reset history":
        user_id = user_id_str or "default_user"
        reset_chat_history(user_id)
        return "Chat history has been successfully reset. You can now start a new inquiry.", 200
        
    # 3. Fetch User Details & Memory
    user_id, user_data, user_details_text, chat_memory = _get_user_and_memory(user_id_str)
    history = chat_memory.buffer if hasattr(chat_memory, 'buffer') else ""
    
    # 4. Extract Drug(s) from current question OR History (Always attempt extraction first)
    # This step handles both explicit drugs and implicit drugs from history/context
    mongo_matches = _extract_drugs_and_check_history(question, history, llm)
    
    
    # --- Intercepts (Priority 1: Non-Drug Queries) ---
    
    # User Details Direct Query Intercept
    user_detail_query = bool(re.search(r'\b(prescriptions|allergies|history|details|profile|weight|height|gender|age)\b', question.lower()))
    
    if user_detail_query and not mongo_matches: 
        print("DEBUG: Intercepted user profile data query. Bypassing RAG.")
        # Logic using USER_DETAIL_PROMPT_TEMPLATE (as in original code block)
        data_type_match = re.search(r'\b(prescriptions|allergies|family history|surgeries|weight|height|gender|age)\b', question.lower())
        data_type = data_type_match.group(0).lower() if data_type_match else "details"
        full_prompt = USER_DETAIL_PROMPT_TEMPLATE.format(history=history, user_details=user_details_text, question=question).replace("[data_type]", data_type) 
        try:
            response_text = llm.invoke(full_prompt).strip()
            chat_memory.save_context({"input": "User: " + question}, {"output": "AI: " + response_text})
            return response_text, 200
        except Exception as e:
            print(f"USER DETAIL LLM error: {e}")
            return "An error occurred while retrieving your profile details. Please try again.", 500

    # General Chat Fallback
    if not mongo_matches:
        # This path is hit if it's NOT a profile query AND no drugs were found.
        print("DEBUG: No drugs found. Falling back to general chat LLM mode.")
        # Logic using GENERAL_PROMPT_TEMPLATE (as in original code block)
        full_prompt = GENERAL_PROMPT_TEMPLATE.format(history=history, question=question)
        try:
            response_text = llm.invoke(full_prompt).strip()
            chat_memory.save_context({"input": "User: " + question}, {"output": "AI: " + response_text})
            return response_text, 200
        except Exception as e:
            print(f"GENERAL LLM error: {e}")
            return "An error occurred during general chat processing. Please try again.", 500


    # --- RAG Logic (Starts here if drug matches were found) ---
    primary_match = mongo_matches[0]
    
    # Logic to ensure the primary drug is the one appearing first in the query for clear interaction questions
    if len(mongo_matches) > 1 and ("take" in question.lower() or "interaction" in question.lower()):
        name0 = primary_match.get("name", "").lower()
        name1 = mongo_matches[1].get("name", "").lower()
        q_lower = question.lower()
        
        idx0 = q_lower.find(name0)
        idx1 = q_lower.find(name1)

        if idx1 > -1 and (idx1 < idx0 or idx0 == -1):
            temp_match = mongo_matches[1]
            mongo_matches[1] = mongo_matches[0]
            mongo_matches[0] = temp_match
            primary_match = mongo_matches[0] 
            print(f"DEBUG: Swapped primary drug to {primary_match.get('name')}")
            
    primary_id = primary_match.get("drugbank_id")
    primary_name = primary_match.get("name", 'N/A')
    
    if not primary_id:
        return f"Found drug **{primary_name}**, but it's missing a DrugBank ID for vector retrieval. I cannot provide a specific answer based on this information.", 200

    # 5. Determine Secondary Drugs for Interaction Check (Handles two drugs or one drug vs. prescriptions)
    secondary_drugs_to_check = _get_secondary_drugs_for_check(mongo_matches, primary_match, user_data)

    # 6. Direct Structured Interaction Check Logic (Highest Priority Context)
    direct_interaction_context, sources_list, secondary_for_rag = _check_interactions(primary_match, secondary_drugs_to_check)
    
    # 7. Determine RAG Intent for Filtering (CRITICAL FIX 1)
    # If a direct, structured interaction was found, or if multiple drugs were in the query, 
    # we need ALL context (exclude_interactions = False).
    if direct_interaction_context or len(mongo_matches) > 1:
        rag_intent = "INTERACTION"
        exclude_interactions = False
    else:
        # For single-drug queries, check the LLM classification to filter out interaction docs for general questions.
        rag_intent = _classify_rag_intent(question, llm)
        exclude_interactions = (rag_intent == "GENERAL_INFO") # Exclude interaction docs for general single-drug queries
        
    # 8. Setup RAG Chain(s) and Retrieve Context 
    context_text = direct_interaction_context 
    final_rag_targets = []
    
    final_rag_targets.append(primary_match)
    if secondary_for_rag and secondary_for_rag.get("drugbank_id") != primary_match.get("drugbank_id"):
        final_rag_targets.append(secondary_for_rag)
        
    print(f"DEBUG: RAG targets set to: {[d.get('name') for d in final_rag_targets]}. Intent: {rag_intent}. Exclude Interactions: {exclude_interactions}.")
    
    # 8B. Run RAG for ALL Identified Targets 
    unique_rag_ids = set()
    
    for drug_doc in final_rag_targets:
        doc_id = drug_doc.get("drugbank_id")
        if doc_id and doc_id not in unique_rag_ids:
            # Pass the exclusion flag to the context retrieval function (CRITICAL FIX 1)
            docs, drug_context = _get_drug_context_rag_docs(drug_doc, question, exclude_interactions) 
            context_text += drug_context
            for doc in docs:
                sources_list.append(doc.metadata.get("id", f"{drug_doc.get('name')} RAG: {doc_id}")) 
            unique_rag_ids.add(doc_id)
            
    # 9. Final Context Check 
    if not context_text:
        return (f"Found drug **{primary_name}**, but I couldn't find any relevant information in the knowledge base. "
                "I cannot provide a specific answer based on the drug information available in my database, but I strongly recommend consulting a healthcare professional."), 200

    # 10. Create the full prompt and Invoke the LLM (CRITICAL FIX 2: Mandatory Focus)
    
    # Determine the name of the secondary drug for the prompt's mandatory focus header
    secondary_name_for_prompt = secondary_for_rag.get('name') if secondary_for_rag else "N/A (Single Drug Query)"

    # NEW: Conditionally set history to empty string if a critical interaction context exists
    history_for_prompt = history
    if direct_interaction_context:
        print("CRITICAL ISOLATION: Zeroing out chat history to prevent hallucination.")
        history_for_prompt = ""

    full_prompt = prompt_template.format(
        history=history_for_prompt, # Use the potentially isolated history
        user_details=user_details_text,
        context=context_text,
        question=question,
        primary_drug_name=primary_name,
        secondary_drug_name=secondary_name_for_prompt
    )

    try:
        response_text = llm.invoke(full_prompt).strip()
        
        # Save context (User: question, AI: response_text)
        chat_memory.save_context({"input": "User: " + question}, {"output": "AI: " + response_text})

        # 11. Format and append source information
        # ... (Source citation logic remains the same) ...
        if sources_list:
            unique_sources = sorted(list(set(sources_list)))
            
            secondary_name_for_source = 'N/A'
            secondary_id_for_source = 'N/A'
            
            if secondary_for_rag and secondary_for_rag.get('drugbank_id'):
                secondary_name_for_source = secondary_for_rag.get('name', 'N/A')
                secondary_id_for_source = secondary_for_rag.get('drugbank_id', 'N/A')
                
            source_citation = "\n\n" + ("-" * 40) + "\n"
            source_citation += f"✨ **Sources from Local DrugBank Database** ✨\n"
            source_citation += f"**Primary Drug:** {primary_name} (ID: {primary_id})\n"
            
            if secondary_name_for_source != 'N/A' and secondary_id_for_source != primary_id: 
                source_citation += f"**Secondary Drug:** {secondary_name_for_source} (ID: {secondary_id_for_source})\n"
                
            source_citation += "Relevant Data Chunks Used (Vector ID or Interaction Source):\n"
            source_citation += "\n".join([f"- {source}" for source in unique_sources])
            
            response_text += source_citation
            
        return response_text, 200
    except Exception as e:
        print(f"RAG LLM error: {e}")
        return "An error occurred during the knowledge retrieval process. Please try again.", 500