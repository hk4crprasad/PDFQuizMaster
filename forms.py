from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, NumberRange
from models_mongo import User

class LoginForm(FlaskForm):
    """Login form for user authentication"""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    """Registration form for new users"""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=4, max=25, message='Username must be between 4 and 25 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Enter a valid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Sign Up')
    
    def validate_username(self, username):
        """Validate username is unique"""
        user = User.get_by_username(username.data)
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')
    
    def validate_email(self, email):
        """Validate email is unique"""
        user = User.get_by_email(email.data)
        if user:
            raise ValidationError('Email already exists. Please use a different one.')

class UploadForm(FlaskForm):
    """Form for uploading PDF files"""
    pdf_file = FileField('PDF File', validators=[
        FileRequired(),
        FileAllowed(['pdf'], 'Only PDF files are allowed!')
    ])
    ocr_method = SelectField('OCR Method for Scanned PDFs', choices=[
        ('auto', 'Auto-detect (use OCR only if needed)'),
        ('local', 'Local OCR (use local OCR tools)'),
        ('azure', 'Azure OCR (best for complex scanned documents)')
    ], default='auto')
    submit = SubmitField('Upload and Generate Questions')

class OJEEExamForm(FlaskForm):
    """Form for configuring OJEE mock exam settings"""
    math_enabled = BooleanField('Include Mathematics Questions', 
                               default=True,
                               render_kw={"class": "form-check-input"})
    math_count = IntegerField('Mathematics Questions', 
                                 validators=[DataRequired(), NumberRange(min=10, max=100)],
                                 default=60,
                                 render_kw={"class": "form-control"})
    computer_enabled = BooleanField('Include Computer Awareness Questions', 
                                   default=True,
                                   render_kw={"class": "form-check-input"})
    computer_count = IntegerField('Computer Awareness Questions', 
                                    validators=[DataRequired(), NumberRange(min=10, max=100)],
                                    default=60,
                                    render_kw={"class": "form-control"})
    time_limit = IntegerField('Exam Duration (minutes)', 
                               validators=[DataRequired(), NumberRange(min=30, max=180)],
                               default=120,
                               render_kw={"class": "form-control"})
    enable_fullscreen = BooleanField('Enable Fullscreen Mode', default=True)
    enable_anticheating = BooleanField('Enable Anti-Cheating Features', default=True)
    show_explanations = BooleanField('Show Answer Explanations After Exam', default=True)
    submit = SubmitField('Generate Mock Exam', render_kw={"class": "btn btn-primary"})

class OJEEExamConfigForm(FlaskForm):
    """Form for configuring a new OJEE mock exam."""
    
    math_questions = IntegerField(
        'Mathematics Questions',
        validators=[DataRequired(), NumberRange(min=5, max=100)],
        render_kw={"class": "form-control", "min": 5, "max": 100, "value": 30},
        default=30
    )
    
    computer_questions = IntegerField(
        'Computer Awareness Questions',
        validators=[DataRequired(), NumberRange(min=5, max=100)],
        render_kw={"class": "form-control", "min": 5, "max": 100, "value": 30},
        default=30
    )
    
    exam_duration = IntegerField(
        'Exam Duration (minutes)',
        validators=[DataRequired(), NumberRange(min=10, max=180)],
        render_kw={"class": "form-control", "min": 10, "max": 180, "value": 90},
        default=90
    )
    
    enable_fullscreen = BooleanField(
        'Enable Fullscreen Mode',
        default=True,
        render_kw={"class": "form-check-input"}
    )
    
    enable_anticheating = BooleanField(
        'Enable Anti-Cheating',
        default=True,
        render_kw={"class": "form-check-input"}
    )
    
    show_explanations = BooleanField(
        'Show Explanations',
        default=True,
        render_kw={"class": "form-check-input"}
    )
    
    submit = SubmitField('Generate Mock Exam', render_kw={"class": "btn btn-primary"})