"""
Mock MongoDB implementation for development purposes when real MongoDB is not available.
This module provides mock classes that mimic the basic functionality of PyMongo.
"""

import logging
import uuid
from datetime import datetime
from bson.objectid import ObjectId

# Set up logging
logger = logging.getLogger(__name__)

class MockMongo:
    """Mock implementation of MongoDB client"""
    def __init__(self):
        self.db = MockDB()

class MockDB:
    """Mock implementation of MongoDB database"""
    def __init__(self):
        self.collections = {
            'users': MockCollection('users'),
            'pdfs': MockCollection('pdfs'),
            'tests': MockCollection('tests'),
            'user_tests': MockCollection('user_tests'),
            'fs.files': MockCollection('fs.files'),
            'fs.chunks': MockCollection('fs.chunks')
        }
        
    def __getattr__(self, name):
        if name in self.collections:
            return self.collections[name]
        raise AttributeError(f"Collection {name} not found")
    
    def command(self, cmd):
        # Mock command to support ping
        if cmd == 'ping':
            return {'ok': 1}
        return None

class MockCollection:
    """Mock implementation of MongoDB collection"""
    def __init__(self, name):
        self.name = name
        self.documents = []
        self.indexes = []
    
    def insert_one(self, document):
        # Add _id if not present
        if '_id' not in document:
            document['_id'] = ObjectId()
        
        # Copy document to avoid reference issues
        doc_copy = document.copy()
        
        # Add to collection
        self.documents.append(doc_copy)
        
        # Return mock result with inserted_id
        class MockInsertResult:
            def __init__(self, _id):
                self.inserted_id = _id
        
        return MockInsertResult(document['_id'])
    
    def find_one(self, query):
        # Handle object id conversion for _id
        if query and '_id' in query and isinstance(query['_id'], ObjectId):
            query_id = query['_id']
            for doc in self.documents:
                if doc.get('_id') == query_id:
                    return doc.copy()
        
        # Handle other queries
        for doc in self.documents:
            matches = True
            for key, value in query.items() if query else {}:
                if key not in doc or doc[key] != value:
                    matches = False
                    break
            if matches:
                return doc.copy()
        
        return None
    
    def find(self, query=None):
        # Return documents matching query
        results = []
        for doc in self.documents:
            if not query:
                results.append(doc.copy())
                continue
                
            matches = True
            for key, value in query.items():
                if key not in doc or doc[key] != value:
                    matches = False
                    break
            if matches:
                results.append(doc.copy())
        
        return MockCursor(results)
    
    def update_one(self, query, update):
        # Find document to update
        for i, doc in enumerate(self.documents):
            matches = True
            for key, value in query.items():
                if key not in doc or doc[key] != value:
                    matches = False
                    break
            
            if matches:
                # Handle $set operator
                if '$set' in update:
                    for key, value in update['$set'].items():
                        # Handle nested fields
                        if '.' in key:
                            parts = key.split('.')
                            curr = doc
                            for part in parts[:-1]:
                                if part not in curr:
                                    curr[part] = {}
                                curr = curr[part]
                            curr[parts[-1]] = value
                        else:
                            doc[key] = value
                
                # Handle other operators as needed
                
                return True
        
        return False
    
    def count_documents(self, query):
        count = 0
        for doc in self.documents:
            matches = True
            for key, value in query.items():
                if key == '$gt':
                    if not doc[key.replace('$gt', '')] > value:
                        matches = False
                        break
                elif key not in doc or doc[key] != value:
                    matches = False
                    break
            if matches:
                count += 1
        return count
    
    def create_index(self, keys, **kwargs):
        # Just store the index definition
        self.indexes.append((keys, kwargs))
        return None
    
    def aggregate(self, pipeline):
        # Very simplified aggregation implementation
        # Just return all documents for now
        return MockCursor(self.documents)

class MockCursor:
    """Mock implementation of MongoDB cursor"""
    def __init__(self, documents):
        self.documents = documents
        self.current = 0
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.current < len(self.documents):
            doc = self.documents[self.current].copy()
            self.current += 1
            return doc
        raise StopIteration

class MockGridFS:
    """Mock implementation of GridFS"""
    def __init__(self, db):
        self.db = db
        self.files = {}
    
    def put(self, data, filename=None, **kwargs):
        file_id = ObjectId()
        self.files[file_id] = {
            'data': data,
            'filename': filename,
            'metadata': kwargs
        }
        
        # Create file document
        file_doc = {
            '_id': file_id,
            'filename': filename,
            'length': len(data),
            'uploadDate': datetime.now()
        }
        self.db.fs.files.insert_one(file_doc)
        
        return file_id
    
    def get(self, file_id):
        if file_id in self.files:
            file_data = self.files[file_id]
            
            # Create a file-like object
            class MockGridOut:
                def __init__(self, data):
                    self.data = data
                    self._buffer = None
                
                def read(self):
                    return self.data['data']
            
            return MockGridOut(file_data)
        return None