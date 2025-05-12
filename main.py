from app import app, socketio
import websocket_events  # Import to register socket events

if __name__ == "__main__":
    # Use socketio.run for development to enable WebSocket functionality
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
    # For production, Gunicorn will use the app object directly
