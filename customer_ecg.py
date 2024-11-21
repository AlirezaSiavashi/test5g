import logging
import time
import uuid
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from sdc11073.wsdiscovery import WSDiscovery
from sdc11073.definitions_sdc import SdcV1Definitions
from sdc11073.consumer import SdcConsumer
from sdc11073.mdib import ConsumerMdib
import socket
import threading

# Provider's IP address and port
PROVIDER_HOST = '141.43.109.188'
PORT = 65432

# Initialize data for plotting
times = []
metric_values = []
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2)
ax.set_ylim(-1.5, 1.5)
ax.set_xlim(0, 10)
ax.set_title('Real-Time ECG Data')
ax.set_xlabel('Time (s)')
ax.set_ylabel('ECG Value')

# Global flag to handle WS-Discovery
found_device = False

def init():
    """Initialize the plot."""
    line.set_data([], [])
    return line,

def update_plot(frame):
    """Update the plot with new data.""" 
    line.set_data(times, metric_values)
    ax.relim()
    ax.autoscale_view()
    if times:
        ax.set_xlim(max(0, times[-1] - 10), times[-1])
    return line,

def start_tcp_client():
    """Connect to the TCP server and receive ECG data."""
    global times, metric_values
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((PROVIDER_HOST, PORT))
        print(f"Connected to TCP server at {PROVIDER_HOST}:{PORT}")
        start_time = time.time()
        while True:
            try:
                data = client_socket.recv(1024).decode()
                if data:
                    print(f"Received ECG data: {data.strip()}")
                    # Parse and update data
                    if "ECG Value:" in data:
                        ecg_value = float(data.split(":")[1].strip())
                        metric_values.append(ecg_value)
                        times.append(time.time() - start_time)
                        # Keep only the last 10 seconds of data
                        if len(times) > 500:
                            times.pop(0)
                            metric_values.pop(0)
            except Exception as e:
                print(f"Error in TCP client: {e}")
                break

def start_ws_discovery():
    """Discover SDC providers and connect to the matching device."""
    global found_device
    my_discovery = WSDiscovery("141.43.3.193")  # Consumer's local IP
    my_discovery.start()

    while not found_device:
        print("Searching for SDC providers...")
        services = my_discovery.search_services(types=SdcV1Definitions.MedicalDeviceTypesFilter)

        # Debugging: Print discovered services
        for one_service in services:
            print(f"Discovered service EPR: {one_service.epr}")

        # Match the provider based on its UUID
        for one_service in services:
            if one_service.epr == uuid.uuid5(uuid.UUID('{cc013678-79f6-403c-998f-3cc0cc050230}'), "12345").urn:
                print(f"Matched service: {one_service}")
                my_client = SdcConsumer.from_wsd_service(one_service, ssl_context_container=None)
                my_client.start_all()
                my_mdib = ConsumerMdib(my_client)
                my_mdib.init_mdib()
                print("Successfully connected to the provider's MDIB.")
                found_device = True
                break

    if not found_device:
        print("No matching provider found.")
    my_discovery.stop()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Start WS-Discovery in a separate thread
    threading.Thread(target=start_ws_discovery, daemon=True).start()

    # Start the TCP client in a separate thread
    threading.Thread(target=start_tcp_client, daemon=True).start()

    # Start real-time ECG plot
    ani = animation.FuncAnimation(fig, update_plot, init_func=init, blit=True, interval=100)
    plt.show()
