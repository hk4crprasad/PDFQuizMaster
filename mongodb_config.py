import os
import logging
import json
from datetime import datetime
from flask import Flask, current_app
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from pymongo import MongoClient
from gridfs import GridFS
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup extensions
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# MongoDB connection string from environment variables
MONGO_URI = os.environ.get("MONGO_URI")
DB_NAME = os.environ.get("DB_NAME", "pdf_test_generator")

# MongoDB client
mongo_client = None
mongo = None
fs = None

def init_mongo(app):
    """Initialize MongoDB and related extensions"""
    global mongo_client, mongo, fs
    
    # Initialize extensions
    bcrypt.init_app(app)
    login_manager.init_app(app)
    
    try:
        # Connect to MongoDB
        mongo_client = MongoClient(MONGO_URI)
        
        # Test connection
        mongo_client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
        
        # Set up database and GridFS
        mongo = mongo_client[DB_NAME]
        fs = GridFS(mongo)
        
        # Create indexes if needed
        mongo.users.create_index([("username", 1)], unique=True)
        mongo.users.create_index([("email", 1)], unique=True)
        
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        # Fall back to mock implementation if connection fails
        init_mock_mongo()

def init_mock_mongo():
    """Initialize mock MongoDB implementation for development"""
    global mongo, fs
    from mock_mongodb import MockMongo, MockGridFS
    
    # Create mock instances
    mongo = MockMongo().db
    fs = MockGridFS(mongo)
    
    logger.info("Mock MongoDB initialized for development")

# Helper function to convert MongoDB ObjectId to string
def stringify_object_id(obj):
    if isinstance(obj, dict):
        for key in obj:
            if isinstance(obj[key], ObjectId):
                obj[key] = str(obj[key])
            elif isinstance(obj[key], (dict, list)):
                stringify_object_id(obj[key])
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, ObjectId):
                obj[i] = str(item)
            elif isinstance(item, (dict, list)):
                stringify_object_id(item)
    return obj