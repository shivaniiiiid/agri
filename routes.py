import os
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse
from sqlalchemy import desc

from app import db
from models import User, Product, Auction, Bid, Transaction
from forms import LoginForm, RegisterForm, ProfileForm, AuctionForm, BidForm, PaymentForm, ProductForm
from utils import check_if_farmer, update_auction_status
import websocket_events  # Import to ensure WebSocket handlers are registered

def register_routes(app):
    
    @app.route('/')
    def index():
        # Get active auctions
        active_auctions = Auction.query.filter_by(is_active=True).order_by(desc(Auction.created_at)).limit(6).all()
        # Get categories
        categories = db.session.query(Product.category).distinct().all()
        categories = [category[0] for category in categories]
        
        return render_template('index.html', 
                               active_auctions=active_auctions,
                               categories=categories,
                               now=datetime.utcnow())
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        form = RegisterForm()
        if form.validate_on_submit():
            user = User(
                username=form.username.data,
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                is_farmer=form.is_farmer.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            flash('Congratulations, you are now registered! Please log in.', 'success')
            return redirect(url_for('login'))
        
        return render_template('register.html', title='Register', form=form)
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            
            if user is None or not user.check_password(form.password.data):
                flash('Invalid email or password', 'danger')
                return redirect(url_for('login'))
            
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('index')
            
            flash('You have been logged in successfully!', 'success')
            return redirect(next_page)
        
        return render_template('login.html', title='Sign In', form=form)
    
    @app.route('/logout')
    def logout():
        logout_user()
        flash('You have been logged out successfully.', 'success')
        return redirect(url_for('index'))
    
    @app.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        form = ProfileForm(obj=current_user)
        
        if form.validate_on_submit():
            current_user.username = form.username.data
            current_user.email = form.email.data
            current_user.first_name = form.first_name.data
            current_user.last_name = form.last_name.data
            current_user.phone = form.phone.data
            current_user.address = form.address.data
            db.session.commit()
            
            flash('Your profile has been updated successfully!', 'success')
            return redirect(url_for('profile'))
        
        # Get user's auctions if they're a farmer
        user_auctions = []
        if current_user.is_farmer:
            user_auctions = Auction.query.filter_by(owner_id=current_user.id).order_by(desc(Auction.created_at)).all()
        
        # Get user's bids if they're a buyer
        user_bids = []
        if not current_user.is_farmer:
            user_bids = Bid.query.filter_by(user_id=current_user.id).order_by(desc(Bid.created_at)).all()
        
        # Get user's transactions
        transactions = []
        if current_user.is_farmer:
            transactions = Transaction.query.filter_by(seller_id=current_user.id).order_by(desc(Transaction.created_at)).all()
        else:
            transactions = Transaction.query.filter_by(buyer_id=current_user.id).order_by(desc(Transaction.created_at)).all()
        
        return render_template('profile.html', 
                               form=form, 
                               user_auctions=user_auctions,
                               user_bids=user_bids,
                               transactions=transactions)
    
    @app.route('/auctions')
    def auctions():
        # Get filters
        search = request.args.get('search', '')
        selected_category = request.args.get('category', '')
        sort = request.args.get('sort', 'latest')
        
        # Build query
        query = Auction.query.filter_by(is_active=True)
        
        # Apply search filter
        if search:
            query = query.filter(Auction.title.contains(search) | Auction.description.contains(search))
        
        # Apply category filter
        if selected_category:
            query = query.join(Product).filter(Product.category == selected_category)
        
        # Apply sorting
        if sort == 'price_low':
            query = query.order_by(Auction.current_price)
        elif sort == 'price_high':
            query = query.order_by(desc(Auction.current_price))
        else:  # latest
            query = query.order_by(desc(Auction.created_at))
        
        # Get all categories for filter options
        categories = db.session.query(Product.category).distinct().all()
        categories = [category[0] for category in categories]
        
        # Execute query
        auctions = query.all()
        
        # Update auction status if needed
        for auction in auctions:
            update_auction_status(auction)
        
        return render_template('auctions.html',
                               auctions=auctions,
                               categories=categories,
                               selected_category=selected_category,
                               search=search,
                               sort=sort,
                               now=datetime.utcnow())
    
    @app.route('/auction/<int:auction_id>', methods=['GET', 'POST'])
    def auction_detail(auction_id):
        auction = Auction.query.get_or_404(auction_id)
        
        # Update auction status if needed
        update_auction_status(auction)
        
        form = BidForm()
        form.auction_id.data = auction_id
        
        if form.validate_on_submit() and current_user.is_authenticated:
            if current_user.is_farmer:
                flash('Farmers cannot place bids. Please use a buyer account.', 'warning')
                return redirect(url_for('auction_detail', auction_id=auction_id))
            
            if not auction.is_active:
                flash('This auction has ended.', 'warning')
                return redirect(url_for('auction_detail', auction_id=auction_id))
            
            if current_user.id == auction.owner_id:
                flash('You cannot bid on your own auction.', 'warning')
                return redirect(url_for('auction_detail', auction_id=auction_id))
            
            min_bid = auction.current_price + 1 if auction.current_price < 100 else auction.current_price + 5
            if form.amount.data < min_bid:
                flash(f'Bid must be at least ₹{min_bid}', 'danger')
                return redirect(url_for('auction_detail', auction_id=auction_id))
            
            bid = Bid(
                amount=form.amount.data,
                auction_id=auction_id,
                user_id=current_user.id
            )
            db.session.add(bid)
            
            # Update auction current price
            auction.current_price = form.amount.data
            db.session.commit()
            
            flash('Your bid has been placed successfully!', 'success')
            return redirect(url_for('auction_detail', auction_id=auction_id))
        
        # Get bid history
        bid_history = Bid.query.filter_by(auction_id=auction_id).order_by(desc(Bid.created_at)).all()
        
        return render_template('auction_detail.html',
                               auction=auction,
                               form=form,
                               bid_history=bid_history,
                               now=datetime.utcnow())
    
    @app.route('/create-auction', methods=['GET', 'POST'])
    @login_required
    @check_if_farmer
    def create_auction():
        form = AuctionForm()
        
        # Populate product choices
        form.product_id.choices = [(p.id, p.name) for p in Product.query.all()]
        
        if form.validate_on_submit():
            auction = Auction(
                title=form.title.data,
                description=form.description.data,
                quantity=form.quantity.data,
                unit=form.unit.data,
                base_price=form.base_price.data,
                current_price=form.base_price.data,
                image_url=form.image_url.data,
                end_time=form.end_time.data,
                owner_id=current_user.id,
                product_id=form.product_id.data
            )
            db.session.add(auction)
            db.session.commit()
            
            flash('Your auction has been created successfully!', 'success')
            return redirect(url_for('auction_detail', auction_id=auction.id))
        
        return render_template('create_auction.html', form=form, is_product_form=False)
    
    @app.route('/add-product', methods=['GET', 'POST'])
    @login_required
    @check_if_farmer
    def add_product():
        form = ProductForm()
        
        if form.validate_on_submit():
            product = Product(
                name=form.name.data,
                category=form.category.data,
                description=form.description.data
            )
            db.session.add(product)
            db.session.commit()
            
            flash('Product added successfully!', 'success')
            return redirect(url_for('create_auction'))
        
        return render_template('create_auction.html', form=form, is_product_form=True)
    
    @app.route('/payment/<int:auction_id>', methods=['GET', 'POST'])
    @login_required
    def payment(auction_id):
        auction = Auction.query.get_or_404(auction_id)
        
        # Check if user is the winner
        if auction.is_active or auction.winner_id != current_user.id:
            flash('You are not authorized to complete this payment.', 'danger')
            return redirect(url_for('auction_detail', auction_id=auction_id))
        
        # Check if payment is already completed
        existing_transaction = Transaction.query.filter_by(
            auction_id=auction_id,
            buyer_id=current_user.id,
            status='completed'
        ).first()
        
        if existing_transaction:
            flash('You have already completed payment for this auction.', 'info')
            return redirect(url_for('profile'))
        
        form = PaymentForm()
        
        # Get the domain for callback URLs
        if os.environ.get('REPLIT_DEPLOYMENT'):
            domain = os.environ.get('REPLIT_DEV_DOMAIN')
        else:
            domain = request.host

        if form.validate_on_submit():
            # Handle different payment methods
            if form.payment_method.data == 'razorpay':
                # Create Razorpay order
                from utils import create_razorpay_order
                order = create_razorpay_order(
                    amount=auction.current_price,
                    auction_id=auction_id,
                    user_id=current_user.id
                )
                
                # Create a pending transaction
                transaction = Transaction(
                    amount=auction.current_price,
                    status='pending',
                    payment_method='razorpay',
                    payment_id=order['id'],
                    auction_id=auction_id,
                    buyer_id=current_user.id,
                    seller_id=auction.owner_id
                )
                db.session.add(transaction)
                db.session.commit()
                
                # Pass order details to template
                return render_template(
                    'payment.html', 
                    form=form, 
                    auction=auction,
                    razorpay_order_id=order['id'],
                    razorpay_key_id=os.environ.get('RAZORPAY_KEY_ID'),
                    razorpay_amount=int(auction.current_price * 100),
                    razorpay_currency='INR',
                    razorpay_name='Agri-Auction',
                    razorpay_description=f'Payment for {auction.title}',
                    razorpay_image='https://i.imgur.com/n5tjHFD.png',
                    razorpay_prefill_name=f'{current_user.first_name} {current_user.last_name}',
                    razorpay_prefill_email=current_user.email,
                    razorpay_prefill_contact=current_user.phone or '',
                    razorpay_callback_url=f"https://{domain}/payment-callback",
                    transaction_id=transaction.id
                )
            elif form.payment_method.data == 'stripe':
                # Create Stripe checkout session
                from utils import create_stripe_checkout_session
                checkout_session = create_stripe_checkout_session(
                    amount=auction.current_price,
                    auction_id=auction_id,
                    user_id=current_user.id,
                    domain=domain,
                    auction_title=auction.title
                )
                
                # Create a pending transaction
                transaction = Transaction(
                    amount=auction.current_price,
                    status='pending',
                    payment_method='stripe',
                    payment_id=checkout_session.id,
                    auction_id=auction_id,
                    buyer_id=current_user.id,
                    seller_id=auction.owner_id
                )
                db.session.add(transaction)
                db.session.commit()
                
                # Pass Stripe checkout URL in template
                return render_template(
                    'payment.html',
                    form=form,
                    auction=auction,
                    stripe_session_id=checkout_session.id,
                    stripe_publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'),
                    stripe_checkout_url=checkout_session.url,
                    transaction_id=transaction.id
                )
        
        return render_template('payment.html', form=form, auction=auction)
        
    @app.route('/payment-callback', methods=['POST'])
    @login_required
    def payment_callback():
        # Get the payment details from the form
        payment_id = request.form.get('razorpay_payment_id')
        order_id = request.form.get('razorpay_order_id')
        signature = request.form.get('razorpay_signature')
        transaction_id = request.form.get('transaction_id')
        
        # Find the transaction
        transaction = Transaction.query.get(transaction_id)
        
        if not transaction:
            flash('Invalid transaction.', 'danger')
            return redirect(url_for('profile'))
        
        # Verify the payment
        from utils import verify_razorpay_payment
        
        if verify_razorpay_payment(payment_id, order_id, signature):
            # Update the transaction
            transaction.status = 'completed'
            transaction.payment_id = payment_id
            db.session.commit()
            
            flash('Payment completed successfully! The seller will be notified.', 'success')
        else:
            # Payment verification failed
            transaction.status = 'failed'
            db.session.commit()
            
            flash('Payment verification failed. Please try again.', 'danger')
        
        return redirect(url_for('profile'))
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        if not current_user.is_admin:
            flash('You do not have permission to access the admin dashboard.', 'danger')
            return redirect(url_for('index'))
        
        # Get stats
        total_users = User.query.count()
        total_farmers = User.query.filter_by(is_farmer=True).count()
        total_buyers = total_users - total_farmers
        
        total_auctions = Auction.query.count()
        active_auctions = Auction.query.filter_by(is_active=True).count()
        
        total_products = Product.query.count()
        total_bids = Bid.query.count()
        
        completed_transactions = Transaction.query.filter_by(status='completed').count()
        total_sales = db.session.query(db.func.sum(Transaction.amount)).filter_by(status='completed').scalar() or 0
        
        # Recent items
        recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
        recent_auctions = Auction.query.order_by(desc(Auction.created_at)).limit(5).all()
        recent_transactions = Transaction.query.order_by(desc(Transaction.created_at)).limit(5).all()
        
        return render_template('dashboard.html',
                               total_users=total_users,
                               total_farmers=total_farmers,
                               total_buyers=total_buyers,
                               total_auctions=total_auctions,
                               active_auctions=active_auctions,
                               total_products=total_products,
                               total_bids=total_bids,
                               completed_transactions=completed_transactions,
                               total_sales=total_sales,
                               recent_users=recent_users,
                               recent_auctions=recent_auctions,
                               recent_transactions=recent_transactions)
    
    @app.route('/api/bid', methods=['POST'])
    @login_required
    def api_bid():
        if not request.is_json:
            return jsonify({'error': 'Invalid JSON'}), 400
        
        data = request.get_json()
        auction_id = data.get('auction_id')
        amount = data.get('amount')
        
        # Debug output
        app.logger.debug(f"Received bid: auction_id={auction_id}, amount={amount}")
        
        if not auction_id or not amount:
            app.logger.error(f"Missing required fields: auction_id={auction_id}, amount={amount}")
            return jsonify({'error': 'Missing required fields'}), 400
        
        try:
            auction_id = int(auction_id)
            amount = float(amount)
        except (ValueError, TypeError):
            app.logger.error(f"Invalid data types: auction_id={auction_id}, amount={amount}")
            return jsonify({'error': 'Invalid bid data'}), 400
        
        auction = Auction.query.get(auction_id)
        if not auction:
            app.logger.error(f"Auction not found: auction_id={auction_id}")
            return jsonify({'error': 'Auction not found'}), 404
        
        if not auction.is_active:
            return jsonify({'error': 'This auction has ended'}), 400
        
        if current_user.is_farmer:
            return jsonify({'error': 'Farmers cannot place bids'}), 403
        
        if current_user.id == auction.owner_id:
            return jsonify({'error': 'You cannot bid on your own auction'}), 403
        
        min_bid = auction.current_price + 1 if auction.current_price < 100 else auction.current_price + 5
        if float(amount) < min_bid:
            return jsonify({'error': f'Bid must be at least ₹{min_bid}'}), 400
        
        try:
            # Create new bid
            bid = Bid(
                amount=float(amount),
                auction_id=auction_id,
                user_id=current_user.id
            )
            db.session.add(bid)
            
            # Update auction current price
            auction.current_price = float(amount)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Your bid has been placed successfully!',
                'current_price': auction.current_price,
                'bidder': current_user.username
            })
        except Exception as e:
            app.logger.error(f"Error placing bid: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'An error occurred while processing your bid'}), 500
    
    @app.route('/stripe-success')
    @login_required
    def stripe_success():
        session_id = request.args.get('session_id')
        if not session_id:
            flash('Invalid session ID.', 'danger')
            return redirect(url_for('profile'))
        
        # Find the transaction
        transaction = Transaction.query.filter_by(payment_id=session_id).first()
        
        if not transaction:
            flash('Invalid transaction.', 'danger')
            return redirect(url_for('profile'))
        
        # Verify the payment
        from utils import verify_stripe_payment
        session = verify_stripe_payment(session_id)
        
        if session:
            # Update the transaction
            transaction.status = 'completed'
            db.session.commit()
            
            flash('Payment completed successfully! The seller will be notified.', 'success')
        else:
            # Payment verification failed
            transaction.status = 'failed'
            db.session.commit()
            
            flash('Payment verification failed. Please try again.', 'danger')
        
        return redirect(url_for('profile'))
    
    @app.route('/stripe-cancel')
    @login_required
    def stripe_cancel():
        flash('Payment cancelled. Please try again.', 'warning')
        return redirect(url_for('profile'))
    
    @app.route('/error')
    def error():
        return render_template('error.html', error_code=500, error_message="This is a test error page.")
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', error_code=404), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('error.html', error_code=500), 500
