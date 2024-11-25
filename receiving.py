from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# Configure the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecg_data.db'
db = SQLAlchemy(app)

# Define the database model
class ECGData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    adc_value = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Create the database table
with app.app_context():
    db.create_all()

@app.route('/upload', methods=['POST'])
def upload_ecg_data():
    adc_value = request.form.get('adc_value')
    if adc_value:
        try:
            # Save data to the database
            ecg_entry = ECGData(adc_value=int(adc_value))
            db.session.add(ecg_entry)
            db.session.commit()
            return "Data saved successfully!", 200
        except Exception as e:
            return str(e), 500
    else:
        return "Invalid data", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
