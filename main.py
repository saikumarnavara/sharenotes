from fastapi import FastAPI, HTTPException, Request
from pymongo import MongoClient, ASCENDING
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware 
import random
import string
import os

app = FastAPI()

# Load environment variables from a .env file
load_dotenv()

# Access the MongoDB URI from the environment variable
MONGO_URI = os.getenv("MONGO_URI")

# Initialize MongoDB Client
client = MongoClient(MONGO_URI)

# Select the database and collection
db = client['sharenotesDB']
collection = db['notes']

# Pydantic model for incoming data (only 'msg' field)
class Note(BaseModel):
    note: str
    response_type: str

# Function to generate a random 5-character alphanumeric ID
def generate_custom_id(length=5):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Create a TTL index on the 'createdAt' field if it doesn't exist
def create_ttl_index():
    indexes = collection.index_information()
    if 'createdAt_1' not in indexes:
        # Create the TTL index, expire documents 48 hours after 'createdAt'
        collection.create_index([('createdAt', ASCENDING)], expireAfterSeconds=172800)  # 48 hours = 172800 seconds

# Ensure the TTL index is created at application startup
create_ttl_index()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins, you can restrict this to specific origins if needed
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

@app.post("/createnote")
def create_note(note: Note, request: Request):
    try:
        # Generate a 5-character unique ID
        custom_id = generate_custom_id()

        # Ensure the custom ID is unique (if ID already exists, regenerate)
        while collection.find_one({"_id": custom_id}) is not None:
            custom_id = generate_custom_id()

        # Insert the message into the MongoDB collection with the custom ID and createdAt timestamp
        result = collection.insert_one({
            "_id": custom_id,
            "msg": note.note,
            "response_type": note.response_type,  # Correctly reference the response_type from the note object
            "createdAt": datetime.utcnow()  # Add timestamp for TTL index
        })

        # Construct the full URL dynamically (remove "/createnote" and use "/getnote")
        base_url = request.url_for('get_note', note_id=custom_id)

        return {"message": "Note created successfully", "note_id": custom_id, "note_url": base_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")


@app.get("/{note_id}")
def get_note(note_id: str):
    try:
        # Fetch the note by its custom ID
        note = collection.find_one({"_id": note_id})
        if note:
            return note
        else:
            raise HTTPException(status_code=404, detail="Note not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving note: {str(e)}")


@app.get("/")
def welcome():
    return {"message": "Welcome to the MongoDB FastAPI app!"}
