from flask import Flask, render_template
from routes import api_blueprint
from flask_cors import CORS
from payment_routes import payment_bp

# Initialize Flask App
app = Flask(__name__, template_folder="templates")
CORS(app)

# Configure database (Example: SQLite)
app.config.from_pyfile('config.py')

# Register API routes from routes.py
app.register_blueprint(api_blueprint)

# Register payment routes from payment_routes.py
app.register_blueprint(payment_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)