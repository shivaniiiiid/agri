# Agri-Auction Platform

An agricultural product auction platform designed to streamline farm-to-market transactions through a modern, interactive online marketplace.

## Features

- User authentication (farmer and buyer roles)
- Real-time auction bidding with WebSocket support
- Product catalog with categories
- Auction creation and management
- Secure payment processing with Razorpay (Indian) and Stripe (International)
- Admin dashboard
- Mobile-responsive design

## Tech Stack

- Backend: Python/Flask
- Database: PostgreSQL
- Frontend: Bootstrap, HTML, CSS, JavaScript
- Real-time: WebSocket with Flask-SocketIO
- Payment: Razorpay and Stripe integrations

## Local Development with Docker

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd agri-auction
   ```

2. Create a `.env` file from the example:
   ```
   cp .env.example .env
   ```

3. Update the `.env` file with your Razorpay and Stripe API keys.

4. Build and start the Docker containers:
   ```
   docker-compose up -d
   ```

5. The application will be available at http://localhost:5000

### Database Migrations

When you make changes to the database models:

```
docker-compose exec web flask db migrate -m "Description of changes"
docker-compose exec web flask db upgrade
```

### Stopping the Application

```
docker-compose down
```

To also remove volumes (database data):
```
docker-compose down -v
```

## Development without Docker

### Prerequisites

- Python 3.11
- PostgreSQL database

### Setup

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables (similar to .env.example).

4. Run the application:
   ```
   gunicorn --bind 0.0.0.0:5000 --worker-class eventlet --reuse-port main:app
   ```

## Testing Payment Integration

For testing the payment gateway integration:

- Razorpay: Use test credentials from the Razorpay dashboard
- Stripe: Use Stripe's test cards (e.g., 4242 4242 4242 4242)

## Contributing

1. Create a feature branch
2. Commit your changes
3. Push to the branch
4. Create a pull request