from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer
import sys
import os

# --- THE CRITICAL IMPORT FIX ---
# Calculate the absolute path to the parent directory and add it to the system path.
# This ensures Python can find 'setup_mongodb' without relying on 'db_scripts' being a package.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now import the setup file directly from the added path
try:
    from db_scripts.setup_mongodb import drug_collection
except ImportError:
    # If the setup_mongodb is one level up (i.e., not in db_scripts folder), try a different path.
    from setup_mongodb import drug_collection 


# NOTE: The dependency on 'drug_collection' from another file is assumed to be working.

# Setup ChromaDB
chroma_client = PersistentClient(path="./chromadb")
collection = chroma_client.get_or_create_collection("drug_data")

# Load model
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_drug_data():
    # --- IMPORTANT: Fetching all actual documents from MongoDB ---
    try:
        # Fetching all documents from the actual MongoDB collection
        documents = list(drug_collection.find({}))
    except Exception as e:
        print(f"❌ Failed to fetch data from MongoDB: {e}")
        sys.exit(1)
    # --------------------------------------------------------------------------

    print(f"✅ Fetched {len(documents)} documents from MongoDB.")

    if not documents:
        print("⚠️ No documents found. Exiting.")
        return

    # --- THE CRITICAL DELETE FIX ---
    # To clear all data in the collection, we must use a filter with an operator 
    # that matches everything, as bare {} is not accepted.
    collection.delete(where={"drugbank_id": {"$ne": "NON_EXISTENT_ID"}})
    print("🧹 Cleared existing ChromaDB collection.")

    for idx, doc in enumerate(documents):
        context_parts = []
        # Ensure 'drugbank_id' exists before processing
        if not doc.get("drugbank_id"):
            print(f"[{idx+1}] ⚠️ Skipped document with missing drugbank_id.")
            continue

        for field in ["description", "drug_interactions", "food_interactions", "targets"]:
            val = doc.get(field)
            if val:
                if isinstance(val, list):
                    # Concatenate list items into a single string for better embedding context
                    context_parts.append(f"{field.replace('_', ' ').title()}: " + ", ".join([str(item) for item in val]))
                else:
                    context_parts.append(f"{field.replace('_', ' ').title()}: {str(val)}")
        
        # We join all fields together to create one large context chunk
        content = "\n".join(context_parts).strip()
        
        if not content:
            print(f"[{idx+1}] ⚠️ Skipped empty content for {doc.get('drugbank_id')}")
            continue

        try:
            embedding = model.encode(content).tolist()
            if not embedding:
                print(f"[{idx+1}] ⚠️ Skipped due to empty embedding for {doc.get('drugbank_id')}")
                continue
        except Exception as e:
            print(f"[{idx+1}] ❌ Embedding failed for {doc.get('drugbank_id')}: {e}")
            continue

        try:
            # --- THE CRITICAL METADATA FIX (still present) ---
            collection.add(
                documents=[content],
                embeddings=[embedding],
                ids=[doc["drugbank_id"]],
                # Now the metadata includes 'drugbank_id' so the retrieval filter works!
                metadatas=[{"name": doc.get("name", "Unknown"), "drugbank_id": doc["drugbank_id"]}]
            )
            print(f"[{idx+1}] ✅ Embedded and stored: {doc.get('name', 'Unknown')} ({doc['drugbank_id']})")
        except Exception as e:
            print(f"[{idx+1}] ❌ Failed to add to ChromaDB for {doc.get('drugbank_id')}: {e}")

if __name__ == "__main__":
    embed_drug_data()
