import logging
from datetime import datetime
from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room, rooms
from app import socketio, db
from models import Auction, Bid, User
from utils import format_currency, update_auction_status

# Setup logger
logger = logging.getLogger(__name__)

@socketio.on('connect')
def handle_connect():
    """Handle client connection to WebSocket."""
    logger.debug(f"Client connected: {request.sid}")
    if current_user.is_authenticated:
        logger.debug(f"Authenticated user connected: {current_user.username}")
    else:
        logger.debug("Anonymous user connected")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection from WebSocket."""
    logger.debug(f"Client disconnected: {request.sid}")

@socketio.on('join_auction')
def handle_join_auction(data):
    """Handle client joining an auction room.
    
    Args:
        data (dict): Contains auction_id to join
    """
    auction_id = data.get('auction_id')
    if not auction_id:
        logger.warning("Missing auction_id in join_auction event")
        return
    
    # Create a room name for this auction
    room = f"auction_{auction_id}"
    
    # Join the room
    join_room(room)
    logger.debug(f"Client {request.sid} joined room {room}")
    
    # Get the auction data to send updated info
    auction = Auction.query.get(auction_id)
    if not auction:
        logger.warning(f"Auction {auction_id} not found")
        return
    
    # Update auction status if needed
    update_auction_status(auction)
    
    # Get highest bid and format for display
    highest_bid = format_currency(auction.current_price) if auction.current_price else "No bids yet"
    
    # Get bid count
    bid_count = len(auction.bids)
    
    # Notify the client about the current auction status
    emit('auction_update', {
        'auction_id': auction_id,
        'current_price': highest_bid,
        'bid_count': bid_count,
        'is_active': auction.is_active,
        'time_remaining': auction.end_time.isoformat() if auction.end_time else None
    }, to=room)

@socketio.on('leave_auction')
def handle_leave_auction(data):
    """Handle client leaving an auction room.
    
    Args:
        data (dict): Contains auction_id to leave
    """
    auction_id = data.get('auction_id')
    if not auction_id:
        return
    
    room = f"auction_{auction_id}"
    leave_room(room)
    logger.debug(f"Client {request.sid} left room {room}")

@socketio.on('place_bid')
def handle_bid(data):
    """Handle bid placement through WebSocket.
    
    Args:
        data (dict): Contains auction_id and amount
    """
    if not current_user.is_authenticated:
        emit('bid_response', {'status': 'error', 'message': 'You must be logged in to place a bid'})
        return
    
    auction_id = data.get('auction_id')
    amount = data.get('amount')
    
    if not auction_id or not amount:
        emit('bid_response', {'status': 'error', 'message': 'Missing auction ID or bid amount'})
        return
    
    try:
        amount = float(amount)
    except ValueError:
        emit('bid_response', {'status': 'error', 'message': 'Invalid bid amount'})
        return
    
    # Get the auction
    auction = Auction.query.get(auction_id)
    if not auction:
        emit('bid_response', {'status': 'error', 'message': 'Auction not found'})
        return
    
    # Check if auction is still active
    if not auction.is_active or auction.is_ended():
        emit('bid_response', {'status': 'error', 'message': 'This auction has ended'})
        return
    
    # Check if the user is the owner of the auction
    if auction.owner_id == current_user.id:
        emit('bid_response', {'status': 'error', 'message': 'You cannot bid on your own auction'})
        return
    
    # Check if the bid amount is higher than the current price
    if amount <= auction.current_price:
        emit('bid_response', {
            'status': 'error', 
            'message': f'Your bid must be higher than the current price ({format_currency(auction.current_price)})'
        })
        return
    
    # Create the bid
    new_bid = Bid(
        amount=amount,
        auction_id=auction_id,
        user_id=current_user.id
    )
    
    # Update the auction's current price
    auction.current_price = amount
    
    # Save to database
    try:
        db.session.add(new_bid)
        db.session.commit()
        logger.info(f"New bid placed: {amount} on auction {auction_id} by user {current_user.id}")
        
        # Room name for this auction
        room = f"auction_{auction_id}"
        
        # Broadcast the updated bid to all users viewing this auction
        emit('auction_update', {
            'auction_id': auction_id,
            'current_price': format_currency(auction.current_price),
            'bid_count': len(auction.bids),
            'last_bidder': current_user.username,
            'timestamp': datetime.utcnow().isoformat(),
            'is_active': auction.is_active
        }, to=room)
        
        # Send success response to the bidder only
        emit('bid_response', {
            'status': 'success',
            'message': f'Your bid of {format_currency(amount)} was placed successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error placing bid: {str(e)}")
        emit('bid_response', {'status': 'error', 'message': 'There was an error placing your bid'})