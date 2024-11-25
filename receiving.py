import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
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
    """Fetch the latest 200 data points (20 seconds of data at 10Hz sampling rate)."""
    with app.app_context():  # Push the Flask application context
        ecg_data = ECGData.query.order_by(ECGData.timestamp.desc()).limit(200).all()
        adc_values = [entry.adc_value for entry in ecg_data][::-1]
        timestamps = [entry.timestamp for entry in ecg_data][::-1]
    return timestamps, adc_values

def smooth_signal(data, window_size=10):
    """Smooth the signal using a moving average."""
    if len(data) < window_size:
        return data
    return np.convolve(data, np.ones(window_size) / window_size, mode='valid')

def live_plot():
    """Plot ECG data dynamically using Matplotlib."""
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title('Live ECG Signal', fontsize=16)
    ax.set_xlabel('Time (seconds)', fontsize=12)
    ax.set_ylabel('ADC Value', fontsize=12)
    line, = ax.plot([], [], label='ECG Signal', color='blue', linewidth=1)
    ax.legend(fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.7)

    def update(frame):
        timestamps, adc_values = fetch_latest_data()
        if timestamps and adc_values:
            # Convert timestamps to relative seconds
            start_time = timestamps[0]
            time_in_seconds = [(t - start_time).total_seconds() for t in timestamps]

            # Smooth the data for clarity
            smoothed_values = smooth_signal(adc_values, window_size=10)

            # Update the plot
            line.set_data(time_in_seconds[:len(smoothed_values)], smoothed_values)
            ax.relim()
            ax.autoscale_view()
        return line,

    ani = animation.FuncAnimation(fig, update, interval=100, cache_frame_data=False)  # Match update rate to 10Hz
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    # Start Flask app in a separate thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)).start()
    # Start live plotting
    live_plot()
