from functools import wraps
import os
import razorpay
import stripe
from flask import flash, redirect, url_for
from flask_login import current_user
from datetime import datetime

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(os.environ.get('RAZORPAY_KEY_ID'), os.environ.get('RAZORPAY_KEY_SECRET'))
)

# Initialize Stripe client
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

def check_if_farmer(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_farmer:
            flash('This page is only available for farmers!', 'warning')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def update_auction_status(auction):
    """
    Updates the auction status if it has ended and sets the winner
    """
    from app import db
    from models import Bid
    
    # Check if auction has ended but is still marked as active
    if auction.is_ended() and auction.is_active:
        auction.is_active = False
        
        # Get the highest bid
        highest_bid = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc()).first()
        
        if highest_bid:
            auction.winner_id = highest_bid.user_id
        
        db.session.commit()
        
    return auction

def format_currency(amount):
    """
    Format a number as currency (Rupees)
    """
    return f"₹{amount:,.2f}"

def time_remaining(end_time):
    """
    Calculate and format the time remaining for an auction
    """
    if end_time < datetime.utcnow():
        return "Ended"
    
    remaining = end_time - datetime.utcnow()
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def create_razorpay_order(amount, auction_id, user_id):
    """
    Create a Razorpay order for payment processing
    
    Args:
        amount: Amount in rupees (will be converted to paise)
        auction_id: ID of the auction being paid for
        user_id: ID of the user making the payment
        
    Returns:
        Dictionary containing Razorpay order details
    """
    # Razorpay expects amount in paise (1 rupee = 100 paise)
    amount_in_paise = int(amount * 100)
    
    # Create a unique receipt ID
    receipt = f"auction_{auction_id}_user_{user_id}_{datetime.utcnow().timestamp()}"
    
    # Create the Razorpay order
    order_data = {
        'amount': amount_in_paise,
        'currency': 'INR',
        'receipt': receipt,
        'notes': {
            'auction_id': str(auction_id),
            'user_id': str(user_id)
        }
    }
    
    # Create the order
    order = razorpay_client.order.create(data=order_data)
    return order

def verify_razorpay_payment(payment_id, order_id, signature):
    """
    Verify the Razorpay payment using signature verification
    
    Args:
        payment_id: Razorpay payment ID
        order_id: Razorpay order ID
        signature: Razorpay signature
        
    Returns:
        Boolean indicating whether payment is valid
    """
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_payment_id': payment_id,
            'razorpay_order_id': order_id,
            'razorpay_signature': signature
        })
        return True
    except Exception:
        return False
        
def create_stripe_checkout_session(amount, auction_id, user_id, domain, auction_title):
    """
    Create a Stripe checkout session for payment processing
    
    Args:
        amount: Amount in rupees (will be converted to cents)
        auction_id: ID of the auction being paid for
        user_id: ID of the user making the payment
        domain: Domain for success and cancel URLs
        auction_title: Title of the auction
        
    Returns:
        Stripe checkout session
    """
    # Stripe expects amount in cents (1 rupee = 100 cents)
    amount_in_cents = int(amount * 100)
    
    # Create a unique ID for this session
    metadata = {
        'auction_id': str(auction_id),
        'user_id': str(user_id)
    }
    
    # Create the checkout session
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'inr',
                'product_data': {
                    'name': f'Payment for {auction_title}',
                },
                'unit_amount': amount_in_cents,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=f'https://{domain}/stripe-success?session_id={{CHECKOUT_SESSION_ID}}',
        cancel_url=f'https://{domain}/stripe-cancel',
        metadata=metadata,
    )
    
    return checkout_session
    
def verify_stripe_payment(session_id):
    """
    Verify the Stripe payment using session ID
    
    Args:
        session_id: Stripe checkout session ID
        
    Returns:
        Session details if payment is complete, None otherwise
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            return session
        return None
    except Exception:
        return None
