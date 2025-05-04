from flask_login import UserMixin
from datetime import datetime
from bson.objectid import ObjectId
from mongodb_config import mongo, login_manager, bcrypt, stringify_object_id
import json

@login_manager.user_loader
def load_user(user_id):
    """Load user from MongoDB by ID for Flask-Login"""
    user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

class User(UserMixin):
    """User model for MongoDB and Flask-Login"""
    
    def __init__(self, user_data):
        self.user_data = user_data
        
    def get_id(self):
        """Return string ID of user for Flask-Login"""
        return str(self.user_data.get('_id'))
    
    @property
    def id(self):
        return self.user_data.get('_id')
    
    @property
    def username(self):
        return self.user_data.get('username')
    
    @property
    def email(self):
        return self.user_data.get('email')
    
    @property
    def created_at(self):
        return self.user_data.get('created_at')
    
    @property
    def is_active(self):
        return self.user_data.get('is_active', True)
    
    @property
    def xp_points(self):
        return self.user_data.get('xp_points', 0)
    
    @property
    def badges(self):
        return self.user_data.get('badges', [])
    
    @property
    def study_stats(self):
        return self.user_data.get('study_stats', {})
    
    @classmethod
    def get_by_username(cls, username):
        """Find user by username"""
        user_data = mongo.db.users.find_one({"username": username})
        if user_data:
            return cls(user_data)
        return None
    
    @classmethod
    def get_by_email(cls, email):
        """Find user by email"""
        user_data = mongo.db.users.find_one({"email": email})
        if user_data:
            return cls(user_data)
        return None
    
    @classmethod
    def create_user(cls, username, email, password):
        """Create a new user with hashed password"""
        # Check if username or email already exists
        if cls.get_by_username(username) or cls.get_by_email(email):
            return None
            
        # Hash password
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Create user document
        user_data = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "created_at": datetime.utcnow(),
            "is_active": True,
            "xp_points": 0,
            "badges": [],
            "study_stats": {
                "tests_taken": 0,
                "avg_score": 0,
                "total_questions": 0,
                "correct_answers": 0,
                "pdfs_processed": 0
            }
        }
        
        # Insert into MongoDB
        result = mongo.db.users.insert_one(user_data)
        user_data['_id'] = result.inserted_id
        
        return cls(user_data)
    
    def verify_password(self, password):
        """Verify password against stored hash"""
        stored_hash = self.user_data.get('password_hash')
        if stored_hash:
            return bcrypt.check_password_hash(stored_hash, password)
        return False
    
    def update_study_stats(self, score, total_questions, correct_answers, test_type=None):
        """Update user study statistics after taking a test"""
        stats = self.study_stats
        
        # Update test count
        tests_taken = stats.get('tests_taken', 0) + 1
        
        # Update total questions and correct answers
        total_q = stats.get('total_questions', 0) + total_questions
        correct_a = stats.get('correct_answers', 0) + correct_answers
        
        # Calculate new average score
        avg_score = ((stats.get('avg_score', 0) * (tests_taken - 1)) + score) / tests_taken
        
        # Update stats in MongoDB
        update_fields = {
            "study_stats.tests_taken": tests_taken,
            "study_stats.avg_score": avg_score,
            "study_stats.total_questions": total_q,
            "study_stats.correct_answers": correct_a
        }
        
        # Add test type specific counters if provided
        if test_type:
            test_type_count = stats.get(f'{test_type}_count', 0) + 1
            update_fields[f"study_stats.{test_type}_count"] = test_type_count
        
        mongo.db.users.update_one(
            {"_id": self.id},
            {"$set": update_fields}
        )
        
        # Update XP points (e.g., 10 XP per correct answer)
        self.add_xp(correct_answers * 10)
        
        # Update local user data
        self.user_data['study_stats'] = {
            "tests_taken": tests_taken,
            "avg_score": avg_score,
            "total_questions": total_q,
            "correct_answers": correct_a,
            "pdfs_processed": stats.get('pdfs_processed', 0)
        }
        
        # Add test type specific counters to local data
        if test_type and f'{test_type}_count' in update_fields:
            self.user_data['study_stats'][f'{test_type}_count'] = test_type_count
    
    def increment_pdfs_processed(self):
        """Increment the number of PDFs processed by the user"""
        pdfs = self.study_stats.get('pdfs_processed', 0) + 1
        
        mongo.db.users.update_one(
            {"_id": self.id},
            {"$set": {"study_stats.pdfs_processed": pdfs}}
        )
        
        # Update local user data
        if 'study_stats' in self.user_data:
            self.user_data['study_stats']['pdfs_processed'] = pdfs
        
        # Add XP for uploading a PDF (e.g., 25 XP)
        self.add_xp(25)
    
    def add_xp(self, points):
        """Add XP points to user and check for badges"""
        current_xp = self.xp_points
        new_xp = current_xp + points
        
        mongo.db.users.update_one(
            {"_id": self.id},
            {"$set": {"xp_points": new_xp}}
        )
        
        # Update local user data
        self.user_data['xp_points'] = new_xp
        
        # Check for level-up badges
        self.check_and_award_badges()
    
    def check_and_award_badges(self):
        """Check and award badges based on user achievements"""
        badges = self.badges.copy() if self.badges else []
        new_badges = []
        
        # XP milestone badges
        xp_badges = {
            "xp_100": {"name": "Scholar Initiate", "description": "Earned 100 XP", "xp_required": 100},
            "xp_500": {"name": "Knowledge Seeker", "description": "Earned 500 XP", "xp_required": 500},
            "xp_1000": {"name": "Master Scholar", "description": "Earned 1000 XP", "xp_required": 1000}
        }
        
        # Check XP badges
        for badge_id, badge in xp_badges.items():
            if self.xp_points >= badge["xp_required"] and badge_id not in badges:
                badges.append(badge_id)
                new_badges.append(badge["name"])
        
        # Test count badges
        test_badges = {
            "tests_5": {"name": "Test Taker", "description": "Completed 5 tests", "tests_required": 5},
            "tests_20": {"name": "Test Expert", "description": "Completed 20 tests", "tests_required": 20},
            "tests_50": {"name": "Test Master", "description": "Completed 50 tests", "tests_required": 50}
        }
        
        # Check test badges
        tests_taken = self.study_stats.get('tests_taken', 0)
        for badge_id, badge in test_badges.items():
            if tests_taken >= badge["tests_required"] and badge_id not in badges:
                badges.append(badge_id)
                new_badges.append(badge["name"])
        
        # Accuracy badges
        if self.study_stats.get('total_questions', 0) >= 50:
            accuracy = self.study_stats.get('correct_answers', 0) / self.study_stats.get('total_questions', 1)
            
            accuracy_badges = {
                "accuracy_70": {"name": "Sharp Mind", "description": "70% accuracy on tests", "accuracy_required": 0.7},
                "accuracy_85": {"name": "Brilliant Mind", "description": "85% accuracy on tests", "accuracy_required": 0.85},
                "accuracy_95": {"name": "Genius", "description": "95% accuracy on tests", "accuracy_required": 0.95}
            }
            
            for badge_id, badge in accuracy_badges.items():
                if accuracy >= badge["accuracy_required"] and badge_id not in badges:
                    badges.append(badge_id)
                    new_badges.append(badge["name"])
        
        # Update badges in MongoDB if new badges were earned
        if len(badges) > len(self.badges or []):
            mongo.db.users.update_one(
                {"_id": self.id},
                {"$set": {"badges": badges}}
            )
            
            # Update local user data
            self.user_data['badges'] = badges
        
        return new_badges

class PDF:
    """PDF model for MongoDB"""
    
    @classmethod
    def create(cls, user_id, filename, file_id, title=None):
        """Create a new PDF document record"""
        pdf_data = {
            "user_id": user_id,
            "filename": filename,
            "file_id": file_id,  # GridFS file ID
            "title": title or filename,
            "uploaded_at": datetime.utcnow()
        }
        
        result = mongo.db.pdfs.insert_one(pdf_data)
        pdf_data['_id'] = result.inserted_id
        
        return pdf_data
    
    @classmethod
    def get_by_id(cls, pdf_id):
        """Get PDF by ID"""
        return mongo.db.pdfs.find_one({"_id": ObjectId(pdf_id)})
    
    @classmethod
    def get_by_user(cls, user_id):
        """Get all PDFs uploaded by a user"""
        cursor = mongo.db.pdfs.find({"user_id": ObjectId(user_id)})
        return list(cursor)

class Test:
    """Test model for MongoDB"""
    
    @classmethod
    def create(cls, pdf_id, questions):
        """Create a new test from PDF and questions"""
        test_data = {
            "pdf_id": pdf_id,
            "questions": questions,
            "created_at": datetime.utcnow()
        }
        
        result = mongo.db.tests.insert_one(test_data)
        test_data['_id'] = result.inserted_id
        
        return test_data
    
    @classmethod
    def get_by_id(cls, test_id):
        """Get test by ID"""
        return mongo.db.tests.find_one({"_id": ObjectId(test_id)})
    
    @classmethod
    def get_by_pdf(cls, pdf_id):
        """Get tests associated with a PDF"""
        cursor = mongo.db.tests.find({"pdf_id": ObjectId(pdf_id)})
        return list(cursor)

class UserTest:
    """User Test (test results) model for MongoDB"""
    
    @classmethod
    def create(cls, user_id, test_id, user_answers, score):
        """Create a new user test record"""
        test_data = {
            "user_id": user_id,
            "test_id": test_id,
            "user_answers": user_answers,
            "score": score,
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow()
        }
        
        result = mongo.db.user_tests.insert_one(test_data)
        test_data['_id'] = result.inserted_id
        
        return test_data
    
    @classmethod
    def get_by_user(cls, user_id):
        """Get all tests taken by a user"""
        cursor = mongo.db.user_tests.find({"user_id": ObjectId(user_id)})
        return list(cursor)
    
    @classmethod
    def get_by_id(cls, user_test_id):
        """Get user test by ID"""
        return mongo.db.user_tests.find_one({"_id": ObjectId(user_test_id)})

class OJEEExam:
    """OJEE Mock Exam model for MongoDB"""
    
    @classmethod
    def create(cls, user_id, settings):
        """Create a new OJEE mock exam"""
        # Generate unique exam ID
        from uuid import uuid4
        
        exam_data = {
            "user_id": user_id,
            "exam_id": str(uuid4()),
            "created_at": datetime.utcnow(),
            "settings": {
                "exam_duration": settings.get("exam_duration", 120),
                "math_questions": settings.get("math_questions", 60),
                "computer_questions": settings.get("computer_questions", 60),
                "enable_fullscreen": settings.get("enable_fullscreen", True),
                "enable_anticheating": settings.get("enable_anticheating", True),
                "show_explanations": settings.get("show_explanations", True)
            },
            "status": "created",
            "questions": None,
            "start_time": None,
            "end_time": None,
            "completed": False,
            "score": None
        }
        
        result = mongo.db.ojee_exams.insert_one(exam_data)
        exam_data["_id"] = result.inserted_id
        
        return exam_data
    
    @classmethod
    def get_by_id(cls, exam_id):
        """Get exam by ID"""
        return mongo.db.ojee_exams.find_one({"exam_id": exam_id})
    
    @classmethod
    def get_by_user(cls, user_id):
        """Get all exams for a user"""
        return list(mongo.db.ojee_exams.find({"user_id": user_id}))
    
    @classmethod
    def update_exam(cls, exam_id, update_data):
        """Update exam data"""
        mongo.db.ojee_exams.update_one(
            {"exam_id": exam_id},
            {"$set": update_data}
        )
    
    @classmethod
    def mark_started(cls, exam_id):
        """Mark exam as started"""
        mongo.db.ojee_exams.update_one(
            {"exam_id": exam_id},
            {"$set": {
                "status": "in_progress",
                "start_time": datetime.utcnow()
            }}
        )
    
    @classmethod
    def mark_completed(cls, exam_id, user_answers, score_data):
        """Mark exam as completed and save results"""
        mongo.db.ojee_exams.update_one(
            {"exam_id": exam_id},
            {"$set": {
                "status": "completed",
                "end_time": datetime.utcnow(),
                "completed": True,
                "user_answers": user_answers,
                "score": score_data
            }}
        )
        
    @classmethod
    def save_questions(cls, exam_id, questions):
        """Save generated questions to exam"""
        mongo.db.ojee_exams.update_one(
            {"exam_id": exam_id},
            {"$set": {
                "questions": json.dumps(questions),
                "status": "ready"
            }}
        )