from flask import Blueprint, render_template, url_for, flash, redirect, request, session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from models_mongo import User
from mongodb_config import mongo
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
auth = Blueprint('auth', __name__)

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    from forms import RegistrationForm
    form = RegistrationForm()
    
    if form.validate_on_submit():
        # Create new user
        user = User.create_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data
        )
        
        if user:
            login_user(user)
            flash(f'Account created successfully. Welcome, {form.username.data}!', 'success')
            
            # Get next page from request args or default to index
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
    
    return render_template('auth/signup.html', form=form)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    from forms import LoginForm
    form = LoginForm()
    
    if form.validate_on_submit():
        # Get user by username
        user = User.get_by_username(form.username.data)
        
        # Verify user and password
        if user and user.verify_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Welcome back, {form.username.data}!', 'success')
            
            # Get next page from request args or default to index
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@auth.route('/profile')
@login_required
def profile():
    """Display user profile"""
    # Get user's PDFs
    user_pdfs = mongo.db.pdfs.find({"user_id": current_user.id})
    
    # Get user's test history with PDF titles
    pipeline = [
        {"$match": {"user_id": current_user.id}},
        {"$lookup": {
            "from": "tests",
            "localField": "test_id",
            "foreignField": "_id",
            "as": "test"
        }},
        {"$unwind": "$test"},
        {"$lookup": {
            "from": "pdfs",
            "localField": "test.pdf_id",
            "foreignField": "_id",
            "as": "pdf"
        }},
        {"$unwind": "$pdf"},
        {"$sort": {"completed_at": -1}},
        {"$project": {
            "_id": 1,
            "score": 1,
            "completed_at": 1,
            "pdf_title": "$pdf.title"
        }}
    ]
    
    test_history = list(mongo.db.user_tests.aggregate(pipeline))
    
    # Get badge details for display
    badge_details = []
    for badge_id in current_user.badges:
        if badge_id.startswith('xp_'):
            if badge_id == 'xp_100':
                badge_details.append({
                    'name': 'Scholar Initiate',
                    'description': 'Earned 100 XP',
                    'icon': 'bi-mortarboard'
                })
            elif badge_id == 'xp_500':
                badge_details.append({
                    'name': 'Knowledge Seeker',
                    'description': 'Earned 500 XP',
                    'icon': 'bi-book'
                })
            elif badge_id == 'xp_1000':
                badge_details.append({
                    'name': 'Master Scholar',
                    'description': 'Earned 1000 XP',
                    'icon': 'bi-award'
                })
        elif badge_id.startswith('tests_'):
            if badge_id == 'tests_5':
                badge_details.append({
                    'name': 'Test Taker',
                    'description': 'Completed 5 tests',
                    'icon': 'bi-journal-check'
                })
            elif badge_id == 'tests_20':
                badge_details.append({
                    'name': 'Test Expert',
                    'description': 'Completed 20 tests',
                    'icon': 'bi-journals'
                })
            elif badge_id == 'tests_50':
                badge_details.append({
                    'name': 'Test Master',
                    'description': 'Completed 50 tests',
                    'icon': 'bi-trophy'
                })
        elif badge_id.startswith('accuracy_'):
            if badge_id == 'accuracy_70':
                badge_details.append({
                    'name': 'Sharp Mind',
                    'description': '70% accuracy on tests',
                    'icon': 'bi-lightning'
                })
            elif badge_id == 'accuracy_85':
                badge_details.append({
                    'name': 'Brilliant Mind',
                    'description': '85% accuracy on tests',
                    'icon': 'bi-lightbulb'
                })
            elif badge_id == 'accuracy_95':
                badge_details.append({
                    'name': 'Genius',
                    'description': '95% accuracy on tests',
                    'icon': 'bi-stars'
                })
    
    # Calculate next level (next badge)
    next_level = None
    current_xp = current_user.xp_points
    
    if current_xp < 100:
        next_level = {
            'name': 'Scholar Initiate',
            'xp_required': 100,
            'progress': (current_xp / 100) * 100
        }
    elif current_xp < 500:
        next_level = {
            'name': 'Knowledge Seeker',
            'xp_required': 500,
            'progress': ((current_xp - 100) / 400) * 100
        }
    elif current_xp < 1000:
        next_level = {
            'name': 'Master Scholar',
            'xp_required': 1000,
            'progress': ((current_xp - 500) / 500) * 100
        }
    
    return render_template(
        'auth/profile.html',
        pdfs=user_pdfs,
        test_history=test_history,
        badges=badge_details,
        next_level=next_level
    )

@auth.route('/recommendations')
@login_required
def recommendations():
    """Show study recommendations based on user performance"""
    # Get user test results with related test and PDF data
    pipeline = [
        {"$match": {"user_id": current_user.id}},
        {"$lookup": {
            "from": "tests",
            "localField": "test_id",
            "foreignField": "_id",
            "as": "test"
        }},
        {"$unwind": "$test"},
        {"$lookup": {
            "from": "pdfs",
            "localField": "test.pdf_id",
            "foreignField": "_id",
            "as": "pdf"
        }},
        {"$unwind": "$pdf"},
        {"$sort": {"score": 1}}  # Sort by lowest scores first
    ]
    
    test_results = list(mongo.db.user_tests.aggregate(pipeline))
    
    # Generate recommendations
    recommendations = []
    topics_to_review = set()
    
    for result in test_results:
        # If score is below 70%, recommend reviewing this PDF
        if result.get('score', 0) < 70:
            pdf_title = result.get('pdf', {}).get('title', 'Unknown Document')
            
            # Check if we don't already have this PDF in our recommendations
            if pdf_title not in topics_to_review:
                topics_to_review.add(pdf_title)
                
                # Add recommendation
                recommendations.append({
                    'type': 'review',
                    'title': f'Review {pdf_title}',
                    'description': f'Your score was {result.get("score")}%. Try studying this material again.',
                    'pdf_id': str(result.get('pdf', {}).get('_id')),
                    'icon': 'bi-book'
                })
    
    # Add general recommendations based on study patterns
    study_stats = current_user.study_stats
    tests_taken = study_stats.get('tests_taken', 0)
    
    if tests_taken < 5:
        recommendations.append({
            'type': 'practice',
            'title': 'Take More Tests',
            'description': 'Practice makes perfect! Try to complete at least 5 tests.',
            'icon': 'bi-journal-check'
        })
    
    # If they have a good amount of XP but low accuracy, recommend focusing on quality
    if current_user.xp_points > 200 and study_stats.get('total_questions', 0) > 0:
        accuracy = study_stats.get('correct_answers', 0) / study_stats.get('total_questions', 1)
        if accuracy < 0.7:
            recommendations.append({
                'type': 'focus',
                'title': 'Focus on Accuracy',
                'description': 'You\'re making good progress, but try to improve your accuracy by reading questions carefully.',
                'icon': 'bi-bullseye'
            })
    
    # If they've only done a few PDFs, encourage more
    if study_stats.get('pdfs_processed', 0) < 3:
        recommendations.append({
            'type': 'expand',
            'title': 'Expand Your Knowledge',
            'description': 'Try uploading more PDFs on different topics to broaden your knowledge.',
            'icon': 'bi-graph-up'
        })
    
    return render_template('auth/recommendations.html', recommendations=recommendations)

@auth.route('/leaderboard')
def leaderboard():
    """Show XP leaderboard of users"""
    # Get top 20 users by XP
    pipeline = [
        {"$sort": {"xp_points": -1}},
        {"$limit": 20},
        {"$project": {
            "_id": 1,
            "username": 1,
            "xp_points": 1,
            "badges": 1,
            "study_stats.tests_taken": 1
        }}
    ]
    
    top_users = list(mongo.db.users.aggregate(pipeline))
    
    # Determine current user's rank if they're not in top 20
    user_rank = None
    if current_user.is_authenticated:
        # Check if user is in top 20
        user_in_top = any(str(user.get('_id')) == current_user.get_id() for user in top_users)
        
        if not user_in_top:
            # Count how many users have more XP than current user
            higher_xp_count = mongo.db.users.count_documents({
                "xp_points": {"$gt": current_user.xp_points}
            })
            user_rank = higher_xp_count + 1
    
    return render_template(
        'auth/leaderboard.html',
        top_users=top_users,
        user_rank=user_rank
    )