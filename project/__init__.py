from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.config['SECRET_KEY'] = 'wiki-game-secret-key' # Ensure this matches the original
CORS(app) # Ensure CORS settings match
socketio = SocketIO(app, cors_allowed_origins="*") # Ensure SocketIO settings match

# Import routes and socket handlers here to avoid circular dependencies
# These imports will typically be at the end of the file
from . import routes
from . import socket_handlers
