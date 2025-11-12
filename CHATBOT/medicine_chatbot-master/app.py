# app.py

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from datetime import datetime

# --- Import chat logic from the separate file ---
from chat_logic import user_collection, handle_chat_query, get_user_details_text

# --- Flask App Initialization ---
app = Flask(__name__)
# Allow CORS from the React frontend (assuming http://localhost:5173)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}) 

# --- User Management API Endpoints ---

@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"detail": "Email and password required"}), 400

    if user_collection.find_one({"email": email}):
        return jsonify({"detail": "Email already registered"}), 409

    hashed_password = generate_password_hash(password)
    user_data = {
        "email": email,
        "password": hashed_password,
        "created_at": datetime.now()
    }
    result = user_collection.insert_one(user_data)
    
    return jsonify({"message": "Signup successful", "user_id": str(result.inserted_id)}), 201

@app.route("/signin", methods=["POST"])
def signin():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"detail": "Email and password required"}), 400

    user = user_collection.find_one({"email": email})
    
    if user and check_password_hash(user["password"], password):
        return jsonify({"message": "Signin successful", "user_id": str(user["_id"])}), 200
    else:
        return jsonify({"detail": "Invalid credentials"}), 401

@app.route("/api/personal-info", methods=["GET", "POST"])
def manage_personal_info():
    # Use 'X-User-ID' header for security (as updated in React)
    user_id_str = request.headers.get("X-User-ID") 

    if not user_id_str:
        return jsonify({"detail": "User ID header is missing"}), 400
    
    try:
        user_id = ObjectId(user_id_str)
    except:
        return jsonify({"detail": "Invalid User ID format"}), 400

    if request.method == "GET":
        user_data = user_collection.find_one({"_id": user_id}, {"password": 0})
        if user_data:
            user_data["_id"] = str(user_data["_id"])
            
            # Format dates for JSON/React
            if "surgeries" in user_data:
                 user_data["surgeries"] = [
                     {**s, "date": s["date"].isoformat() if isinstance(s.get("date"), datetime) else s.get("date")}
                     for s in user_data["surgeries"]
                 ]
            return jsonify(user_data), 200
        return jsonify({"detail": "User not found"}), 404

    elif request.method == "POST":
        data = request.get_json()
        
        # Convert date strings to datetime objects for MongoDB storage
        if "surgeries" in data:
            for s in data.get("surgeries", []):
                if s.get("date"):
                    try:
                        s["date"] = datetime.strptime(s["date"], "%Y-%m-%d")
                    except ValueError:
                        return jsonify({"detail": "Invalid date format for surgery. Use YYYY-MM-DD"}), 400

        data.pop("email", None)
        data.pop("password", None)
        
        result = user_collection.update_one(
            {"_id": user_id},
            {"$set": data}
        )

        if result.matched_count == 0:
            return jsonify({"detail": "User not found"}), 404
        
        return jsonify({"message": "Personal information updated successfully"}), 200

# --- Chat API Endpoint ---

@app.route("/chat", methods=["GET"])
def chat_query():
    question = request.args.get("question")
    # Retrieve user ID from the custom header
    user_id_str = request.headers.get("X-User-ID") 

    if not question:
        return jsonify({"reply": "Please provide a question."}), 400

    # 💡 MODIFICATION: Call the refactored logic function
    response_text, status_code = handle_chat_query(question, user_id_str)
    
    return jsonify({"reply": response_text}), status_code
    
if __name__ == "__main__":
    app.run(port=8000, debug=True)