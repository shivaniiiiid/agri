from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms import FloatField, SelectField, DateTimeField, HiddenField, DecimalField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, URL, Optional
from datetime import datetime, timedelta

from models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    first_name = StringField('First Name', validators=[Length(max=64)])
    last_name = StringField('Last Name', validators=[Length(max=64)])
    is_farmer = BooleanField('Register as Farmer')
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose another one.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use another one.')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[Length(max=64)])
    last_name = StringField('Last Name', validators=[Length(max=64)])
    phone = StringField('Phone', validators=[Length(max=20)])
    address = TextAreaField('Address', validators=[Length(max=256)])
    submit = SubmitField('Update Profile')

class AuctionForm(FlaskForm):
    title = StringField('Auction Title', validators=[DataRequired(), Length(max=100)])
    product_id = SelectField('Product', coerce=int, validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    quantity = FloatField('Quantity', validators=[DataRequired()])
    unit = SelectField('Unit', choices=[
        ('kg', 'Kilograms (kg)'), 
        ('ton', 'Tons'), 
        ('lb', 'Pounds (lb)'),
        ('g', 'Grams (g)'),
        ('l', 'Liters (l)'),
        ('piece', 'Piece(s)')
    ], validators=[DataRequired()])
    base_price = DecimalField('Base Price (₹)', validators=[DataRequired()])
    image_url = StringField('Image URL', validators=[Optional(), URL()])
    end_time = DateTimeField('End Time', format='%Y-%m-%d %H:%M', 
                          validators=[DataRequired()],
                          default=lambda: datetime.utcnow() + timedelta(days=7))
    submit = SubmitField('Create Auction')

class BidForm(FlaskForm):
    amount = DecimalField('Bid Amount (₹)', validators=[DataRequired()])
    auction_id = HiddenField('Auction ID', validators=[DataRequired()])
    submit = SubmitField('Place Bid')

class PaymentForm(FlaskForm):
    payment_method = SelectField('Payment Method', 
                               choices=[
                                   ('razorpay', 'Razorpay - Cards, UPI, Wallets & Netbanking'),
                                   ('stripe', 'Stripe - International Cards')
                               ],
                               validators=[DataRequired()])
    submit = SubmitField('Proceed to Payment')

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired(), Length(max=100)])
    category = SelectField('Category', choices=[
        ('fruits', 'Fruits'),
        ('vegetables', 'Vegetables'),
        ('grains', 'Grains'),
        ('dairy', 'Dairy'),
        ('livestock', 'Livestock'),
        ('seeds', 'Seeds'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Length(max=1000)])
    submit = SubmitField('Add Product')
