import numpy as np
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecg_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define the database model
class ECGData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    adc_value = db.Column(db.Integer, nullable=False)  #it is better to convert the type to float
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create the database table
with app.app_context():
    db.create_all()

@app.route('/upload', methods=['POST'])
def upload_ecg_data():
    """
    Endpoint to upload ECG data.
    Expects POST requests with 'adc_value' as a form parameter.
    """
    try:
        adc_value = request.form.get('adc_value')
        if adc_value is None:
            return jsonify({"error": "Missing adc_value parameter"}), 400

        # Convert and validate adc_value
        adc_value = int(adc_value)
        
        # Save to the database
        ecg_entry = ECGData(adc_value=adc_value)
        db.session.add(ecg_entry)
        db.session.commit()

        return jsonify({"message": "Data saved successfully!"}), 200
    except ValueError:
        return jsonify({"error": "adc_value must be an integer"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
