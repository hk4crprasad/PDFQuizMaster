from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
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