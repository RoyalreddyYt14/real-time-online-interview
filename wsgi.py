# WSGI entry point for production deployment
# This file allows gunicorn to serve the Flask application

from app import socketio, app

# For gunicorn with eventlet worker
if __name__ == "__main__":
    socketio.run(app)
