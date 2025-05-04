import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import uuid
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import PDF processing utilities
from utils.pdf_processor import extract_text_from_pdf
from utils.question_generator import generate_questions

# Initialize Flask application
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "your-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///pdftestmaker.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max upload size

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Import models after db initialization
with app.app_context():
    from models import User, PDF, Test, UserTest
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'pdf_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        file = request.files['pdf_file']
        
        # If user does not select file, browser also
        # submits an empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Generate unique filename
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            # Store file info in session
            session['uploaded_file'] = {
                'original_name': filename,
                'path': filepath
            }
            
            try:
                # Process PDF directly in Flask
                logger.info(f"Processing PDF: {filename}")
                
                # Extract text from PDF
                text, title = extract_text_from_pdf(filepath)
                
                if not text:
                    flash('Could not extract text from PDF', 'danger')
                    return redirect(request.url)
                
                # Generate questions using LangChain and Azure OpenAI
                logger.info("Generating questions")
                questions = generate_questions(text)
                
                # Save to database - we'll store everything in the database to avoid session size limits
                with app.app_context():
                    pdf_record = PDF(
                        filename=filename,
                        filepath=filepath,
                        title=title or filename
                    )
                    db.session.add(pdf_record)
                    db.session.commit()
                    
                    # Create test from questions
                    test = Test(
                        pdf_id=pdf_record.id,
                        questions=json.dumps(questions),
                        created_at=datetime.now()
                    )
                    db.session.add(test)
                    db.session.commit()
                    
                    # Store only test ID and PDF title in session to avoid session size limits
                    session['test_id'] = test.id
                    session['pdf_title'] = title or filename
                
                flash('File uploaded and processed successfully!', 'success')
                return redirect(url_for('take_test'))
                
            except Exception as e:
                flash(f'Error processing PDF: {str(e)}', 'danger')
                logger.error(f"Processing Error: {str(e)}")
                
            return redirect(url_for('upload'))
    
    return render_template('upload.html')

@app.route('/test')
def take_test():
    test_id = session.get('test_id')
    pdf_title = session.get('pdf_title', 'Untitled Document')
    
    if not test_id:
        flash('No test available. Please upload a PDF first.', 'warning')
        return redirect(url_for('upload'))
    
    # Get questions from database using test_id
    test = Test.query.get(test_id)
    if not test:
        flash('Test not found. Please upload a PDF again.', 'warning')
        return redirect(url_for('upload'))
    
    # Load questions from JSON
    questions = json.loads(test.questions)
    
    # Store in session for form submission
    session['questions'] = questions
    
    return render_template('test.html', questions=questions, pdf_title=pdf_title)

@app.route('/submit_test', methods=['POST'])
def submit_test():
    if request.method == 'POST':
        user_answers = {}
        questions = session.get('questions', [])
        
        # Get answers from form
        for i, _ in enumerate(questions):
            answer_key = f'answer_{i}'
            if answer_key in request.form:
                user_answers[i] = request.form[answer_key]
        
        # Calculate score
        correct_count = 0
        results = []
        
        for i, question in enumerate(questions):
            user_answer = user_answers.get(i, '')
            correct_answer = question['answer']
            is_correct = user_answer == correct_answer
            
            if is_correct:
                correct_count += 1
            
            results.append({
                'question': question['question'],
                'options': question['options'],
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })
        
        total_questions = len(questions)
        score_percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        
        # Get test ID from session
        test_id = session.get('test_id')
        
        # Store test results
        if test_id:
            user_test = UserTest(
                test_id=test_id,
                user_answers=json.dumps(user_answers),
                score=score_percentage,
                completed_at=datetime.now()
            )
            db.session.add(user_test)
            db.session.commit()
        
        # Store results in session for results page
        session['test_results'] = {
            'results': results,
            'score': score_percentage,
            'correct_count': correct_count,
            'total_questions': total_questions
        }
        
        return redirect(url_for('show_results'))
    
    return redirect(url_for('take_test'))

@app.route('/results')
def show_results():
    test_results = session.get('test_results')
    pdf_title = session.get('pdf_title', 'Untitled Document')
    
    if not test_results:
        flash('No test results available', 'warning')
        return redirect(url_for('upload'))
    
    return render_template(
        'results.html', 
        results=test_results['results'],
        score=test_results['score'],
        correct_count=test_results['correct_count'],
        total_questions=test_results['total_questions'],
        pdf_title=pdf_title
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
