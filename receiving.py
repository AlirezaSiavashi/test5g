from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import time
import threading

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
            ecg_entry = ECGData(adc_value=int(adc_value))
            db.session.add(ecg_entry)
            db.session.commit()
            return "Data saved successfully!", 200
        except Exception as e:
            return str(e), 500
    else:
        return "Invalid data", 400

def fetch_latest_data():
    """Fetch the latest 1000 data points from the database."""
    with app.app_context():  # Push the Flask application context
        ecg_data = ECGData.query.order_by(ECGData.timestamp.desc()).limit(1000).all()
        adc_values = [entry.adc_value for entry in ecg_data][::-1]
        timestamps = [entry.timestamp for entry in ecg_data][::-1]
    return timestamps, adc_values

def live_plot():
    """Plot ECG data dynamically using Matplotlib."""
    fig, ax = plt.subplots()
    ax.set_title('ECG Signal')
    ax.set_xlabel('Time')
    ax.set_ylabel('ADC Value')
    line, = ax.plot([], [], label='ECG Signal', color='blue')
    ax.legend()
    ax.grid(True)

    def update(frame):
        timestamps, adc_values = fetch_latest_data()
        if timestamps and adc_values:
            line.set_data(range(len(adc_values)), adc_values)
            ax.relim()
            ax.autoscale_view()
        return line,

    ani = animation.FuncAnimation(fig, update, interval=500, cache_frame_data=False)
    plt.show()

if __name__ == '__main__':
    # Start Flask app in a separate thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)).start()
    # Start live plotting
    live_plot()
