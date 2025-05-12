// Socket.io instance
let socket = null;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Real-time countdown for auctions
    updateCountdowns();
    setInterval(updateCountdowns, 1000);

    // Initialize Socket.IO if on an auction page
    initializeSocketIO();
    
    // Handle bid form submission via WebSocket
    const bidForm = document.getElementById('bid-form');
    if (bidForm) {
        bidForm.addEventListener('submit', handleBidSubmission);
    }

    // Handle image error
    const auctionImages = document.querySelectorAll('.auction-image');
    auctionImages.forEach(img => {
        img.addEventListener('error', function() {
            this.src = 'https://via.placeholder.com/400x300?text=No+Image+Available';
        });
    });
});

/**
 * Update all countdown timers on the page
 */
function updateCountdowns() {
    const countdownElements = document.querySelectorAll('.countdown');
    
    countdownElements.forEach(element => {
        const endTime = new Date(element.dataset.endTime).getTime();
        const now = new Date().getTime();
        const timeLeft = endTime - now;
        
        if (timeLeft <= 0) {
            element.innerHTML = 'Auction ended';
            element.classList.add('text-danger');
            
            // Disable bid button if it exists
            const bidButton = document.querySelector('#bid-button');
            if (bidButton) {
                bidButton.disabled = true;
                bidButton.textContent = 'Auction Ended';
            }
            
            return;
        }
        
        // Calculate time units
        const days = Math.floor(timeLeft / (1000 * 60 * 60 * 24));
        const hours = Math.floor((timeLeft % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((timeLeft % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeLeft % (1000 * 60)) / 1000);
        
        // Format the countdown based on remaining time
        let countdownText = '';
        if (days > 0) {
            countdownText = `${days}d ${hours}h ${minutes}m`;
        } else if (hours > 0) {
            countdownText = `${hours}h ${minutes}m ${seconds}s`;
        } else if (minutes > 0) {
            countdownText = `${minutes}m ${seconds}s`;
        } else {
            countdownText = `${seconds}s`;
            element.classList.add('text-danger');
        }
        
        element.textContent = countdownText;
    });
}

/**
 * Initialize Socket.IO connection and event handlers
 */
function initializeSocketIO() {
    // Check if we're on an auction detail page
    const auctionIdElement = document.getElementById('auction_id');
    if (!auctionIdElement) {
        return; // Not on an auction detail page
    }

    // Get the auction ID
    const auctionId = auctionIdElement.value;
    
    // Initialize Socket.IO connection
    socket = io();
    
    // Connection event
    socket.on('connect', function() {
        console.log('WebSocket connected');
        
        // Join the auction room
        socket.emit('join_auction', { auction_id: auctionId });
    });
    
    // Disconnect event
    socket.on('disconnect', function() {
        console.log('WebSocket disconnected');
    });
    
    // Listen for auction updates
    socket.on('auction_update', function(data) {
        console.log('Received auction update:', data);
        if (data.auction_id == auctionId) {
            updateAuctionUI(data);
        }
    });
    
    // Listen for bid responses
    socket.on('bid_response', function(data) {
        console.log('Received bid response:', data);
        showBidResponse(data);
    });
    
    // When leaving the page, leave the auction room
    window.addEventListener('beforeunload', function() {
        if (socket) {
            socket.emit('leave_auction', { auction_id: auctionId });
        }
    });
}

/**
 * Update the auction UI with the latest data
 * @param {Object} data - Auction update data
 */
function updateAuctionUI(data) {
    // Update current price
    const currentPriceElement = document.getElementById('current-price');
    if (currentPriceElement && data.current_price) {
        currentPriceElement.textContent = data.current_price;
    }
    
    // Update bid count if element exists
    const bidCountElement = document.getElementById('bid-count');
    if (bidCountElement && data.bid_count) {
        bidCountElement.textContent = data.bid_count;
    }
    
    // Update bid history if a new bid came in
    if (data.last_bidder) {
        const bidHistoryElement = document.getElementById('bid-history');
        if (bidHistoryElement) {
            const newBidItem = document.createElement('div');
            newBidItem.className = 'bid-item';
            newBidItem.innerHTML = `
                <div class="bid-user">${data.last_bidder}</div>
                <div class="bid-amount">${data.current_price}</div>
                <div class="bid-time">Just now</div>
            `;
            bidHistoryElement.insertBefore(newBidItem, bidHistoryElement.firstChild);
        }
        
        // Update the minimum bid amount in the input
        const bidInput = document.getElementById('amount');
        if (bidInput) {
            // Extract the numeric value from the price string (removing ₹ symbol and commas)
            const currentPrice = parseFloat(data.current_price.replace('₹', '').replace(/,/g, ''));
            bidInput.value = currentPrice < 100 ? (currentPrice + 1).toFixed(2) : (currentPrice + 5).toFixed(2);
        }
    }
    
    // If auction is no longer active, disable bidding
    if (data.is_active === false) {
        const bidButton = document.querySelector('#bid-button');
        if (bidButton) {
            bidButton.disabled = true;
            bidButton.textContent = 'Auction Ended';
        }
        
        const countdownElement = document.querySelector('.countdown');
        if (countdownElement) {
            countdownElement.innerHTML = 'Auction ended';
            countdownElement.classList.add('text-danger');
        }
    }
}

/**
 * Show bid response messages
 * @param {Object} data - Response data with status and message
 */
function showBidResponse(data) {
    const alertContainer = document.getElementById('bid-alert');
    if (!alertContainer) return;
    
    if (data.status === 'success') {
        alertContainer.innerHTML = `
            <div class="alert alert-success">
                ${data.message}
            </div>
        `;
    } else {
        alertContainer.innerHTML = `
            <div class="alert alert-danger">
                ${data.message}
            </div>
        `;
    }
}

/**
 * Handle bid form submission via WebSocket
 * @param {Event} e - Form submit event
 */
function handleBidSubmission(e) {
    e.preventDefault();
    
    const form = e.target;
    const auctionId = document.getElementById('auction_id').value;
    const bidAmount = form.elements['amount'].value;
    const submitButton = form.querySelector('button[type="submit"]');
    const alertContainer = document.getElementById('bid-alert');
    
    console.log("Submitting bid with auction_id:", auctionId, "amount:", bidAmount);
    
    // Disable button during submission
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
    
    // Clear previous alerts
    if (alertContainer) {
        alertContainer.innerHTML = '';
    }
    
    // Check if we have a socket connection
    if (socket && socket.connected) {
        // Emit bid event via WebSocket
        socket.emit('place_bid', {
            auction_id: auctionId,
            amount: bidAmount
        });
        
        // Re-enable button after a short delay (the response will be handled by event listeners)
        setTimeout(() => {
            submitButton.disabled = false;
            submitButton.textContent = 'Place Bid';
        }, 500);
    } else {
        // Fallback to AJAX if WebSocket is not connected
        console.log("WebSocket not connected, falling back to AJAX");
        
        // Send AJAX request
        fetch('/api/bid', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                auction_id: auctionId,
                amount: bidAmount
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update UI on success
                const currentPriceElement = document.getElementById('current-price');
                const bidHistoryElement = document.getElementById('bid-history');
                
                if (currentPriceElement) {
                    currentPriceElement.textContent = `₹${parseFloat(data.current_price).toFixed(2)}`;
                }
                
                // Add new bid to history
                if (bidHistoryElement) {
                    const newBidItem = document.createElement('div');
                    newBidItem.className = 'bid-item';
                    newBidItem.innerHTML = `
                        <div class="bid-user">${data.bidder}</div>
                        <div class="bid-amount">₹${parseFloat(data.current_price).toFixed(2)}</div>
                        <div class="bid-time">Just now</div>
                    `;
                    bidHistoryElement.insertBefore(newBidItem, bidHistoryElement.firstChild);
                }
                
                // Show success message
                if (alertContainer) {
                    alertContainer.innerHTML = `
                        <div class="alert alert-success">
                            ${data.message}
                        </div>
                    `;
                }
                
                // Increment the bid input for next bid
                const bidInput = form.elements['amount'];
                const currentBid = parseFloat(data.current_price);
                bidInput.value = currentBid < 100 ? (currentBid + 1).toFixed(2) : (currentBid + 5).toFixed(2);
                
            } else {
                // Show error message
                if (alertContainer) {
                    alertContainer.innerHTML = `
                        <div class="alert alert-danger">
                            ${data.error}
                        </div>
                    `;
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            if (alertContainer) {
                alertContainer.innerHTML = `
                    <div class="alert alert-danger">
                        An error occurred while processing your bid. Please try again.
                    </div>
                `;
            }
        })
        .finally(() => {
            // Re-enable button
            submitButton.disabled = false;
            submitButton.textContent = 'Place Bid';
        });
    }
}
