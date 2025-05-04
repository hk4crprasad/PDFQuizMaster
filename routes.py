import os
import json
import logging
import uuid
import threading
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from io import BytesIO

from main import app
from mongodb_config import mongo, stringify_object_id, fs
from models_mongo import User, PDF, Test, UserTest
from utils.pdf_processor import extract_text_from_pdf
from utils.question_generator import generate_questions

# Set up logging
logger = logging.getLogger(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/tests')
@login_required
def tests():
    """Show user's PDFs and their test status"""
    # Get user's PDFs from MongoDB
    user_pdfs = PDF.get_by_user(current_user.id)
    
    # Determine the status of each PDF
    for pdf in user_pdfs:
        # Check if it has a test
        tests = Test.get_by_pdf(ObjectId(pdf['_id']))
        if not tests:
            # No tests yet, might still be processing
            # Get PDF processing status from processing_status if available
            if pdf.get('file_id') is None:
                pdf['status'] = 'processing'
            else:
                pdf['status'] = 'failed'  # Has file_id but no tests
        else:
            pdf['status'] = 'ready'
    
    return render_template('tests.html', pdfs=user_pdfs)

@app.route('/process_pdf/<pdf_id>')
@login_required
def process_pdf_from_id(pdf_id):
    """Show processing status for a specific PDF"""
    # Get PDF from MongoDB
    pdf_data = PDF.get_by_id(ObjectId(pdf_id))
    
    if not pdf_data:
        flash('PDF not found', 'danger')
        return redirect(url_for('tests'))
    
    # Check if this PDF belongs to the current user
    if pdf_data['user_id'] != current_user.id:
        flash('You do not have permission to access this PDF', 'danger')
        return redirect(url_for('tests'))
    
    # Create a unique ID for tracking progress if one doesn't exist in session
    processing_pdf_id = session.get('processing_pdf_id')
    if not processing_pdf_id:
        processing_pdf_id = str(uuid.uuid4())
        session['processing_pdf_id'] = processing_pdf_id
    
    return render_template('processing.html', 
                          pdf_id=processing_pdf_id, 
                          pdf_title=pdf_data.get('title', 'PDF Document'))

@app.route('/delete_pdf', methods=['POST'])
@login_required
def delete_pdf():
    """Delete a PDF and its associated tests"""
    # Create a form just for CSRF validation
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        pdf_id = request.form.get('pdf_id')
        
        if not pdf_id:
            flash('No PDF specified', 'danger')
            return redirect(url_for('tests'))
        
        # Get PDF from MongoDB
        pdf_data = PDF.get_by_id(ObjectId(pdf_id))
        
        if not pdf_data:
            flash('PDF not found', 'danger')
            return redirect(url_for('tests'))
        
        # Check if this PDF belongs to the current user
        if pdf_data['user_id'] != current_user.id:
            flash('You do not have permission to delete this PDF', 'danger')
            return redirect(url_for('tests'))
        
        try:
            # Delete file from GridFS if it exists
            if pdf_data.get('file_id'):
                fs.delete(pdf_data['file_id'])
            
            # Delete all tests associated with this PDF
            # First get all the tests
            tests = Test.get_by_pdf(ObjectId(pdf_id))
            
            for test in tests:
                # Delete all user tests associated with this test
                mongo.db.user_tests.delete_many({'test_id': test['_id']})
                
                # Delete the test
                mongo.db.tests.delete_one({'_id': test['_id']})
            
            # Delete the PDF record
            mongo.db.pdfs.delete_one({'_id': ObjectId(pdf_id)})
            
            flash('PDF and associated tests deleted successfully', 'success')
            
        except Exception as e:
            logger.error(f"Error deleting PDF: {str(e)}")
            flash(f'Error deleting PDF: {str(e)}', 'danger')
        
    return redirect(url_for('tests'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload PDF file and generate questions"""
    from forms import UploadForm
    form = UploadForm()
    
    if form.validate_on_submit():
        file = form.pdf_file.data
        ocr_method = form.ocr_method.data
        
        if file and allowed_file(file.filename):
            # Generate unique filename and PDF ID
            filename = secure_filename(file.filename)
            pdf_id = str(uuid.uuid4())
            unique_filename = f"{pdf_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            try:
                # Start processing PDF in background
                logger.info(f"Processing PDF: {filename} with OCR method: {ocr_method}")
                
                # Create PDF document in MongoDB
                pdf_record = PDF.create(
                    user_id=current_user.id,
                    filename=filename,
                    file_id=None,  # Will be updated after processing
                    title=filename
                )
                
                # Store PDF ID and path in session for processing page
                session['processing_pdf_id'] = pdf_id
                session['processing_pdf_path'] = filepath
                session['processing_pdf_record_id'] = str(pdf_record['_id'])
                session['processing_pdf_title'] = filename
                session['processing_ocr_method'] = ocr_method  # Store OCR method in session
                
                # Redirect to processing page
                return redirect(url_for('process_pdf'))
                
            except Exception as e:
                flash(f'Error uploading PDF: {str(e)}', 'danger')
                logger.error(f"Upload Error: {str(e)}")
                
                # Clean up local file
                if os.path.exists(filepath):
                    os.remove(filepath)
                    
            return redirect(url_for('upload'))
    
    return render_template('upload.html', form=form)

@app.route('/process_pdf')
@login_required
def process_pdf():
    """Show PDF processing status and start processing in background"""
    # Get PDF info from session
    pdf_id = session.get('processing_pdf_id')
    pdf_path = session.get('processing_pdf_path')
    pdf_record_id = session.get('processing_pdf_record_id')
    pdf_title = session.get('processing_pdf_title', 'Unknown Document')
    ocr_method = session.get('processing_ocr_method', 'auto')
    
    if not pdf_id or not pdf_path or not pdf_record_id:
        flash('No PDF file found for processing', 'danger')
        return redirect(url_for('upload'))
    
    # Get current user ID to pass to the background thread
    user_id = current_user.get_id()
    
    # Start processing in a background thread
    threading.Thread(target=process_pdf_background, args=(
        pdf_id, pdf_path, pdf_record_id, pdf_title, user_id, ocr_method
    )).start()
    
    return render_template('processing.html', pdf_id=pdf_id, pdf_title=pdf_title)

@app.route('/pdf_status')
@login_required
def pdf_status():
    """Return PDF processing status as JSON"""
    pdf_id = request.args.get('id')
    
    if not pdf_id:
        return jsonify({'error': 'No PDF ID provided'}), 400
    
    # Get status from pdf_processor
    from utils.pdf_processor import processing_status
    
    status = processing_status.get(pdf_id, {
        'step': 1,
        'progress': 0,
        'status': 'Initializing...',
        'complete': False
    })
    
    # Check if test is ready
    test_id = session.get('test_id')
    if test_id and status.get('progress', 0) >= 90:
        status['complete'] = True
    
    return jsonify(status)

def process_pdf_background(pdf_id: str, pdf_path: str, pdf_record_id: str, pdf_title: str, user_id: str, ocr_method: str = 'auto'):
    """Process PDF in background thread"""
    try:
        # Determine if Azure OCR should be used
        use_azure_ocr = ocr_method == 'azure'
        
        # Extract text from PDF with selected OCR method
        logger.info(f"Extracting text with OCR method: {ocr_method}")
        text, title = extract_text_from_pdf(pdf_path, pdf_id, use_azure_ocr=use_azure_ocr)
        
        if not text:
            logger.error(f"Could not extract text from PDF: {pdf_path}")
            from utils.pdf_processor import processing_status
            processing_status[pdf_id] = {
                'step': 1,
                'progress': 0,
                'status': 'Error: Could not extract text from PDF',
                'complete': True
            }
            return
        
        # Update PDF title if extracted from document
        if title and title != pdf_title:
            mongo.db.pdfs.update_one(
                {"_id": ObjectId(pdf_record_id)},
                {"$set": {"title": title}}
            )
            pdf_title = title
        
        # Update processing status
        from utils.pdf_processor import processing_status
        processing_status[pdf_id]['progress'] = 75
        processing_status[pdf_id]['status'] = 'Generating questions'
        
        # Generate questions
        logger.info("Generating questions")
        questions = generate_questions(text)
        
        # Update processing status
        processing_status[pdf_id]['progress'] = 85
        processing_status[pdf_id]['status'] = 'Storing file'
        
        # Store file in MongoDB using GridFS
        with open(pdf_path, 'rb') as pdf_file:
            file_id = fs.put(pdf_file.read(), filename=pdf_title)
        
        # Update PDF record with file_id
        mongo.db.pdfs.update_one(
            {"_id": ObjectId(pdf_record_id)},
            {"$set": {"file_id": file_id}}
        )
        
        # Create test from questions
        test = Test.create(
            pdf_id=ObjectId(pdf_record_id),
            questions=json.dumps(questions)
        )
        
        # Update user stats - Get user from ID instead of using current_user
        if user_id:
            user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
            if user_data:
                user = User(user_data)
                user.increment_pdfs_processed()
                logger.info(f"Updated stats for user: {user.username}")
            else:
                logger.error(f"User not found with ID: {user_id}")
        
        # Store test ID in session (used by processing page to redirect)
        from flask import session
        session['test_id'] = str(test['_id'])
        session['pdf_title'] = pdf_title
        
        # Update processing status to complete
        processing_status[pdf_id]['step'] = 4
        processing_status[pdf_id]['progress'] = 100
        processing_status[pdf_id]['status'] = 'Complete'
        processing_status[pdf_id]['complete'] = True
        
        # Clean up local file after processing
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        
        # Clean up OCR file if it exists
        ocr_path = f"{pdf_path}_ocr.pdf"
        if os.path.exists(ocr_path):
            os.remove(ocr_path)
            
        # Clean up Azure OCR chunk files if they exist
        chunks_dir = os.path.join(os.getcwd(), "chunks")
        if os.path.exists(chunks_dir):
            import shutil
            try:
                shutil.rmtree(chunks_dir)
            except Exception as e:
                logger.warning(f"Could not remove Azure OCR chunks directory: {str(e)}")
            
        logger.info(f"PDF processing completed successfully: {pdf_title}")
        
    except Exception as e:
        logger.error(f"Error in background PDF processing: {str(e)}")
        
        # Update processing status with error
        from utils.pdf_processor import processing_status
        processing_status[pdf_id] = {
            'step': 1,
            'progress': 0,
            'status': f'Error: {str(e)}',
            'complete': True
        }
        
        # Clean up local file
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

@app.route('/test')
@login_required
def take_test():
    """Take a test based on uploaded PDF"""
    test_id = session.get('test_id')
    pdf_title = session.get('pdf_title', 'Untitled Document')
    
    if not test_id:
        flash('No test available. Please upload a PDF first.', 'warning')
        return redirect(url_for('upload'))
    
    # Get test from MongoDB
    test_data = Test.get_by_id(ObjectId(test_id))
    if not test_data:
        flash('Test not found. Please upload a PDF again.', 'warning')
        return redirect(url_for('upload'))
    
    # Load questions from JSON
    questions = json.loads(test_data['questions'])
    
    # Store only the test_id in session, not the entire questions object
    # We'll retrieve questions from the database again when needed
    
    return render_template('test.html', questions=questions, pdf_title=pdf_title)

@app.route('/test/<pdf_id>')
@login_required
def take_specific_test(pdf_id):
    """Take a test for a specific PDF"""
    # Get PDF document
    pdf_data = PDF.get_by_id(ObjectId(pdf_id))
    if not pdf_data:
        flash('PDF not found.', 'warning')
        return redirect(url_for('auth.profile'))
    
    # Get test for this PDF
    tests = Test.get_by_pdf(ObjectId(pdf_data['_id']))
    if not tests:
        flash('No test found for this PDF.', 'warning')
        return redirect(url_for('auth.profile'))
    
    # Use the most recent test
    test_data = tests[0]
    
    # Load questions from JSON
    questions = json.loads(test_data['questions'])
    
    # Store only test ID in session
    session['test_id'] = str(test_data['_id'])
    session['pdf_title'] = pdf_data['title']
    
    return render_template('test.html', questions=questions, pdf_title=pdf_data['title'])

@app.route('/submit_test', methods=['POST'])
@login_required
def submit_test():
    """Handle test submission"""
    # Create a form just for CSRF validation
    from flask_wtf import FlaskForm
    form = FlaskForm()
    
    if form.validate_on_submit():
        test_id = session.get('test_id')
        
        if not test_id:
            flash('Test data not found. Please try again.', 'danger')
            return redirect(url_for('upload'))
        
        # Get test data from database instead of session
        test_data = Test.get_by_id(ObjectId(test_id))
        if not test_data:
            flash('Test not found. Please try again.', 'danger')
            return redirect(url_for('upload'))
            
        # Load questions from the database
        questions = json.loads(test_data['questions'])
        user_answers = {}
        
        # Get answers from form
        for i, _ in enumerate(questions):
            answer_key = f'answer_{i}'
            if answer_key in request.form:
                user_answers[str(i)] = request.form[answer_key]
        
        # Calculate score
        correct_count = 0
        results = []
        
        for i, question in enumerate(questions):
            user_answer = user_answers.get(str(i), '')
            correct_answer = question['answer']
            is_correct = user_answer == correct_answer
            
            if is_correct:
                correct_count += 1
            
            results.append({
                'question': question['question'],
                'options': question.get('options', {}),
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct
            })
        
        total_questions = len(questions)
        score_percentage = (correct_count / total_questions) * 100 if total_questions > 0 else 0
        
        # Create user test record in MongoDB
        user_test = UserTest.create(
            user_id=current_user.id,
            test_id=ObjectId(test_id),
            user_answers=json.dumps(user_answers),
            score=score_percentage
        )
        
        # Update user study stats
        current_user.update_study_stats(
            score=score_percentage,
            total_questions=total_questions,
            correct_answers=correct_count
        )
        
        # Store only minimal results data in session
        result_id = str(user_test['_id'])
        session['result_id'] = result_id
        
        return redirect(url_for('show_results'))
    else:
        # If form validation fails (CSRF issue)
        flash('Form validation failed. Please try again.', 'danger')
    
    return redirect(url_for('take_test'))

@app.route('/results')
@login_required
def show_results():
    """Show test results"""
    result_id = session.get('result_id')
    test_id = session.get('test_id')
    pdf_title = session.get('pdf_title', 'Untitled Document')
    
    # First, try to get results by result_id (new method)
    if result_id:
        # Get user test record from MongoDB
        user_test = UserTest.get_by_id(ObjectId(result_id))
        if user_test:
            # Get the test details to access questions
            test_data = Test.get_by_id(user_test['test_id'])
            if test_data:
                questions = json.loads(test_data['questions'])
                user_answers = json.loads(user_test['user_answers'])
                
                # Recreate results array
                results = []
                correct_count = 0
                
                for i, question in enumerate(questions):
                    user_answer = user_answers.get(str(i), '')
                    correct_answer = question['answer']
                    is_correct = user_answer == correct_answer
                    
                    if is_correct:
                        correct_count += 1
                    
                    results.append({
                        'question': question['question'],
                        'options': question.get('options', {}),
                        'user_answer': user_answer,
                        'correct_answer': correct_answer,
                        'is_correct': is_correct
                    })
                
                total_questions = len(questions)
                score = user_test['score']
                
                # Get PDF title if not already set
                if pdf_title == 'Untitled Document' and test_data:
                    pdf_data = PDF.get_by_id(test_data['pdf_id'])
                    if pdf_data:
                        pdf_title = pdf_data['title']
                
                # Get new badges earned (if any)
                new_badges = current_user.check_and_award_badges()
                
                return render_template(
                    'results.html', 
                    results=results,
                    score=score,
                    correct_count=correct_count,
                    total_questions=total_questions,
                    pdf_title=pdf_title,
                    new_badges=new_badges
                )
    
    # Fallback to using session data (legacy method)
    test_results = session.get('test_results')
    if not test_results:
        flash('No test results available', 'warning')
        return redirect(url_for('upload'))
    
    # Get new badges earned (if any)
    new_badges = current_user.check_and_award_badges()
    
    return render_template(
        'results.html', 
        results=test_results['results'],
        score=test_results['score'],
        correct_count=test_results['correct_count'],
        total_questions=test_results['total_questions'],
        pdf_title=pdf_title,
        new_badges=new_badges
    )

@app.route('/download_pdf/<pdf_id>')
@login_required
def download_pdf(pdf_id):
    """Download a PDF file"""
    try:
        # Get PDF document
        pdf_data = PDF.get_by_id(ObjectId(pdf_id))
        if not pdf_data:
            flash('PDF not found.', 'warning')
            return redirect(url_for('auth.profile'))
        
        # Check if user is allowed to download this PDF
        if str(pdf_data['user_id']) != current_user.get_id():
            flash('You do not have permission to download this PDF.', 'danger')
            return redirect(url_for('auth.profile'))
        
        # Get file from GridFS
        file_data = fs.get(pdf_data['file_id'])
        if not file_data:
            flash('File not found in storage.', 'danger')
            return redirect(url_for('auth.profile'))
        
        # Return file for download
        return send_file(
            BytesIO(file_data.read()),
            download_name=pdf_data['filename'],
            as_attachment=True,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        flash(f'Error downloading file: {str(e)}', 'danger')
        logger.error(f"Download Error: {str(e)}")
        return redirect(url_for('auth.profile'))

@app.route('/ojee', methods=['GET', 'POST'])
@login_required
def ojee_exam_config():
    """Configure and generate OJEE mock exam"""
    from forms import OJEEExamForm
    from models_mongo import OJEEExam
    
    form = OJEEExamForm()
    
    if form.validate_on_submit():
        # Get form data
        # Adjust question counts based on enabled options
        math_count = form.math_count.data if form.math_enabled.data else 0
        computer_count = form.computer_count.data if form.computer_enabled.data else 0
        
        settings = {
            "exam_duration": form.time_limit.data,
            "math_questions": math_count,
            "computer_questions": computer_count,
            "enable_fullscreen": form.enable_fullscreen.data,
            "enable_anticheating": form.enable_anticheating.data,
            "show_explanations": form.show_explanations.data
        }
        
        # Create exam in database
        exam_data = OJEEExam.create(current_user.id, settings)
        
        # Store exam_id in session
        session['ojee_exam_id'] = exam_data['exam_id']
        
        # Redirect to processing page
        return redirect(url_for('ojee_exam_generate'))
    
    return render_template('ojee/config.html', form=form)

@app.route('/ojee/generate', methods=['GET'])
@login_required
def ojee_exam_generate():
    """Generate questions for OJEE mock exam"""
    from models_mongo import OJEEExam
    from utils.question_generator import generate_ojee_questions
    import json
    
    exam_id = session.get('ojee_exam_id')
    if not exam_id:
        flash('No exam configuration found. Please start over.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    exam_data = OJEEExam.get_by_id(exam_id)
    if not exam_data:
        flash('Exam not found. Please create a new exam.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    if request.method == 'GET':
        if exam_data['status'] == 'ready':
            # Questions already generated, proceed to exam
            return redirect(url_for('ojee_exam_take'))
            
        # Show processing page
        return render_template('ojee/processing.html', exam_id=exam_id)

@app.route('/ojee/generate/status', methods=['GET'])
@login_required
def ojee_exam_generate_status():
    """Check and update OJEE exam generation status"""
    from models_mongo import OJEEExam
    from utils.question_generator import generate_ojee_questions
    import json
    import threading
    
    # Get exam_id from query param first, fall back to session if not provided
    exam_id = request.args.get('exam_id') or session.get('ojee_exam_id')
    if not exam_id:
        return jsonify({'status': 'error', 'message': 'No exam configuration found'})
    
    exam_data = OJEEExam.get_by_id(exam_id)
    if not exam_data:
        return jsonify({'status': 'error', 'message': 'Exam not found'})
    
    if exam_data['status'] == 'created':
        # Start generating questions in background
        def generate_and_save():
            try:
                # Use the unified generate_ojee_questions function
                all_questions = generate_ojee_questions(
                    math_count=exam_data['settings']['math_questions'],
                    computer_count=exam_data['settings']['computer_questions']
                )
                
                # Save questions to database
                OJEEExam.save_questions(exam_id, all_questions)
                logger.info(f"OJEE exam questions generated successfully for exam {exam_id}")
                
            except Exception as e:
                logger.error(f"Error generating OJEE exam questions: {str(e)}")
                OJEEExam.update_exam(exam_id, {"status": "error"})
        
        # Start background thread for question generation
        threading.Thread(target=generate_and_save).start()
        
        # Update status to processing
        OJEEExam.update_exam(exam_id, {"status": "processing"})
        return jsonify({'status': 'processing', 'message': 'Started generating questions'})
    
    # Return current status
    return jsonify({
        'status': exam_data['status'],
        'message': 'Questions generated successfully' if exam_data['status'] == 'ready' else 'Still processing'
    })

@app.route('/ojee/take', methods=['GET'])
@login_required
def ojee_exam_take():
    """Take OJEE mock exam"""
    from models_mongo import OJEEExam
    
    exam_id = session.get('ojee_exam_id')
    if not exam_id:
        flash('No exam configuration found. Please start over.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    exam_data = OJEEExam.get_by_id(exam_id)
    if not exam_data or exam_data['status'] != 'ready':
        flash('Exam is not ready. Please wait for question generation to complete.', 'warning')
        return redirect(url_for('ojee_exam_generate'))
    
    # Mark exam as started if not already
    if exam_data['status'] == 'ready':
        OJEEExam.mark_started(exam_id)
    
    # Load questions from database
    questions = json.loads(exam_data['questions'])
    
    # Add properties that the template expects to access directly
    exam_data['math_count'] = exam_data['settings']['math_questions']
    exam_data['computer_count'] = exam_data['settings']['computer_questions']
    exam_data['time_limit'] = exam_data['settings']['exam_duration']
    
    return render_template('ojee/exam.html', 
                          exam=exam_data, 
                          questions=questions,
                          math_questions=questions['mathematics'],
                          computer_questions=questions['computer_awareness'])

@app.route('/ojee/submit', methods=['POST'])
@login_required
def ojee_exam_submit():
    """Handle OJEE mock exam submission"""
    from models_mongo import OJEEExam
    
    exam_id = session.get('ojee_exam_id')
    if not exam_id:
        flash('No exam found. Please start a new exam.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    exam_data = OJEEExam.get_by_id(exam_id)
    if not exam_data:
        flash('Exam not found. Please create a new exam.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    # Get answers from form
    user_answers = {
        'mathematics': {},
        'computer_awareness': {}
    }
    
    questions = json.loads(exam_data['questions'])
    
    # Process mathematics answers
    for i, _ in enumerate(questions['mathematics']):
        answer_key = f'math_answer_{i}'
        if answer_key in request.form:
            user_answers['mathematics'][str(i)] = request.form[answer_key]
    
    # Process computer awareness answers
    for i, _ in enumerate(questions['computer_awareness']):
        answer_key = f'comp_answer_{i}'
        if answer_key in request.form:
            user_answers['computer_awareness'][str(i)] = request.form[answer_key]
    
    # Calculate scores
    math_correct = 0
    math_total = len(questions['mathematics'])
    
    for i, question in enumerate(questions['mathematics']):
        user_answer = user_answers['mathematics'].get(str(i), '')
        if user_answer == question['answer']:
            math_correct += 1
    
    comp_correct = 0
    comp_total = len(questions['computer_awareness'])
    
    for i, question in enumerate(questions['computer_awareness']):
        user_answer = user_answers['computer_awareness'].get(str(i), '')
        if user_answer == question['answer']:
            comp_correct += 1
    
    total_correct = math_correct + comp_correct
    total_questions = math_total + comp_total
    
    score_data = {
        'math_correct': math_correct,
        'math_total': math_total,
        'math_percentage': (math_correct / math_total * 100) if math_total > 0 else 0,
        'comp_correct': comp_correct,
        'comp_total': comp_total,
        'comp_percentage': (comp_correct / comp_total * 100) if comp_total > 0 else 0,
        'total_correct': total_correct,
        'total_questions': total_questions,
        'total_percentage': (total_correct / total_questions * 100) if total_questions > 0 else 0
    }
    
    # Save results to database
    OJEEExam.mark_completed(exam_id, user_answers, score_data)
    
    # Update user study stats
    current_user.update_study_stats(
        score=score_data['total_percentage'],
        total_questions=total_questions,
        correct_answers=total_correct,
        test_type='ojee_mock'
    )
    
    # Store results in session for results page
    session['ojee_results'] = {
        'exam_id': exam_id,
        'score_data': score_data
    }
    
    return redirect(url_for('ojee_exam_results'))

@app.route('/ojee/results', methods=['GET'])
@login_required
def ojee_exam_results():
    """Display OJEE mock exam results"""
    from models_mongo import OJEEExam
    
    results_data = session.get('ojee_results')
    if not results_data:
        flash('No exam results found. Please take an exam first.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    exam_id = results_data['exam_id']
    exam_data = OJEEExam.get_by_id(exam_id)
    
    if not exam_data:
        flash('Exam not found. Please create a new exam.', 'warning')
        return redirect(url_for('ojee_exam_config'))
    
    questions = json.loads(exam_data['questions'])
    user_answers = exam_data.get('user_answers', {})
    score_data = exam_data.get('score', results_data['score_data'])
    show_explanations = exam_data['settings'].get('show_explanations', True)
    
    # Create results data structure
    math_results = []
    for i, question in enumerate(questions['mathematics']):
        user_answer = user_answers.get('mathematics', {}).get(str(i), '')
        is_correct = user_answer == question['answer']
        
        math_results.append({
            'question': question['question'],
            'options': question['options'],
            'user_answer': user_answer,
            'correct_answer': question['answer'],
            'is_correct': is_correct,
            'explanation': question.get('explanation', '')
        })
    
    comp_results = []
    for i, question in enumerate(questions['computer_awareness']):
        user_answer = user_answers.get('computer_awareness', {}).get(str(i), '')
        is_correct = user_answer == question['answer']
        
        comp_results.append({
            'question': question['question'],
            'options': question['options'],
            'user_answer': user_answer,
            'correct_answer': question['answer'],
            'is_correct': is_correct,
            'explanation': question.get('explanation', '')
        })
    
    # Calculate exam duration
    start_time = exam_data.get('start_time')
    end_time = exam_data.get('end_time')
    duration_minutes = 0
    time_per_question = 0
    
    if start_time and end_time:
        duration = (end_time - start_time).total_seconds()
        duration_minutes = round(duration / 60, 1)
        total_questions = score_data['total_questions']
        time_per_question = round(duration / total_questions) if total_questions > 0 else 0
    
    # Prepare strengths and weaknesses
    strengths = []
    weaknesses = []
    
    # Mathematics performance
    math_percentage = score_data.get('math_percentage', 0)
    if math_percentage >= 70:
        strengths.append("Strong performance in Mathematics section")
    elif math_percentage <= 40:
        weaknesses.append("Mathematics section needs improvement")
        
    # Computer awareness performance
    comp_percentage = score_data.get('comp_percentage', 0)
    if comp_percentage >= 70:
        strengths.append("Strong performance in Computer Awareness section")
    elif comp_percentage <= 40:
        weaknesses.append("Computer Awareness section needs improvement")
    
    # Time management
    if time_per_question > 60:  # more than 60 seconds per question
        weaknesses.append("Time management - spent too long on questions")
    elif time_per_question < 20:  # less than 20 seconds per question
        weaknesses.append("May be rushing through questions too quickly")
    else:
        strengths.append("Good time management")
    
    # Overall score
    total_percentage = score_data.get('total_percentage', 0)
    if total_percentage >= 75:
        strengths.append("Excellent overall performance")
    elif total_percentage <= 35:
        weaknesses.append("General understanding of topics needs improvement")
    
    # Default topic data
    topic_data = [
        {"topic": "Algebra", "score": 75},
        {"topic": "Geometry", "score": 60},
        {"topic": "Computer Basics", "score": 85},
        {"topic": "Programming", "score": 40},
    ]
    
    # Prepare the result object for the template
    result = {
        'total_score': round(score_data.get('total_percentage', 0)),
        'total_correct': score_data.get('total_correct', 0),
        'total_questions': score_data.get('total_questions', 0),
        'math_score': round(score_data.get('math_percentage', 0)),
        'math_correct': score_data.get('math_correct', 0),
        'math_total': score_data.get('math_total', 0),
        'computer_score': round(score_data.get('comp_percentage', 0)),
        'computer_correct': score_data.get('comp_correct', 0),
        'computer_total': score_data.get('comp_total', 0),
        'duration_minutes': duration_minutes,
        'time_per_question': time_per_question,
        'strengths': strengths,
        'weaknesses': weaknesses,
        'topic_data': topic_data,
        'all_questions': math_results + comp_results,
        'incorrect_questions': [q for q in math_results + comp_results if not q['is_correct']],
        'math_questions': math_results,
        'computer_questions': comp_results
    }

    return render_template('ojee/results.html',
                         exam=exam_data,
                         result=result,
                         score_data=score_data,
                         math_results=math_results,
                         comp_results=comp_results,
                         show_questions=show_explanations)

@app.route('/ojee/history', methods=['GET'])
@login_required
def ojee_exam_history():
    """Show history of OJEE mock exams taken by user"""
    from models_mongo import OJEEExam
    
    user_exams = OJEEExam.get_by_user(current_user.id)
    completed_exams = [exam for exam in user_exams if exam.get('completed', False)]
    
    return render_template('ojee/history.html', exams=completed_exams)

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500