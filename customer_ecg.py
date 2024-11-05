import logging
import time
import uuid
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from sdc11073.xml_types import pm_types, msg_types
from sdc11073.xml_types import pm_qnames as pm
from sdc11073.xml_types.actions import periodic_actions
from sdc11073.wsdiscovery import WSDiscovery
from sdc11073.definitions_sdc import SdcV1Definitions
from sdc11073.consumer import SdcConsumer
from sdc11073.mdib import ConsumerMdib
from sdc11073 import observableproperties
from sdc11073.loghelper import basic_logging_setup
import socket
import threading

# Provider UUID to connect
baseUUID = uuid.UUID('{cc013678-79f6-403c-998f-3cc0cc050230}')
device_A_UUID = uuid.uuid5(baseUUID, "12345")

# Plotting setup
times = []
metric_values = []
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2)
ax.set_ylim(-1, 1)  # Adjust limits for expected ECG range
ax.set_xlim(0, 10)  # Initial X-axis limit
ax.set_title('Metric Value Over Time')
ax.set_xlabel('Time (s)')
ax.set_ylabel('Metric Value')

# Initialize plot
def init():
    line.set_data([], [])
    return line,

# Update plot with new values
def update_plot(frame):
    line.set_data(times, metric_values)
    ax.relim()
    ax.autoscale_view()  # Automatically adjust view to new data
    ax.set_xlim(max(0, times[-1] - 10), times[-1])  # Slide x-axis as time progresses
    return line,

# Callback for metric updates
def on_metric_update(metrics_by_handle: dict):
    for handle, metric in metrics_by_handle.items():
        metric_value = metric.MetricValue.Value  # Access the correct attribute
        timestamp = time.time() - start_time  # Time relative to start

        print(f"Got update on: {handle} with value: {metric_value}")
        
        times.append(timestamp)
        metric_values.append(float(metric_value))  # Ensure numeric values for plotting

        # Limit the list length to keep the plot manageable
        if len(times) > 100:
            times.pop(0)
            metric_values.pop(0)

# Ensemble context setup
def set_ensemble_context(mdib: ConsumerMdib, sdc_consumer: SdcConsumer) -> None:
    # Attempt to set ensemble context on the device
    print("Trying to set ensemble context of device A")
    ensemble_descriptor_container = mdib.descriptions.NODETYPE.get_one(pm.EnsembleContextDescriptor)
    context_client = sdc_consumer.context_service_client
    operation_handle = None
    for op_descr in mdib.descriptions.NODETYPE.get(pm.SetContextStateOperationDescriptor, []):
        if op_descr.OperationTarget == ensemble_descriptor_container.Handle:
            operation_handle = op_descr.Handle
    new_ensemble_context = context_client.mk_proposed_context_object(ensemble_descriptor_container.Handle)
    new_ensemble_context.ContextAssociation = pm_types.ContextAssociation.ASSOCIATED
    new_ensemble_context.Identification = [
        pm_types.InstanceIdentifier(root="1.2.3", extension_string="SupervisorSuperEnsemble")]
    response = context_client.set_context_state(operation_handle, [new_ensemble_context])
    result: msg_types.OperationInvokedReportPart = response.result()
    if result.InvocationInfo.InvocationState not in (msg_types.InvocationState.FINISHED,
                                                     msg_types.InvocationState.FINISHED_MOD):
        print(f'set ensemble context state failed: {result.InvocationInfo.InvocationState}, '
              f'error = {result.InvocationInfo.InvocationError}')
    else:
        print('set ensemble context was successful.')

# TCP Client for receiving additional data if required
def start_tcp_client():
    host, port = '127.0.0.1', 65432
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((host, port))
        print(f"Connected to TCP server at {host}:{port}")
        while True:
            data = client_socket.recv(1024).decode()
            if data:
                print(f"Received ECG data from provider: {data}")

if __name__ == '__main__':
    basic_logging_setup(level=logging.INFO)
    start_time = time.time()  # Set start time for relative timestamping
    my_discovery = WSDiscovery("127.0.0.1")
    my_discovery.start()
    
    # Start searching for SDC providers
    found_device = False
    while not found_device:
        print('Searching for SDC providers...')
        services = my_discovery.search_services(types=SdcV1Definitions.MedicalDeviceTypesFilter)
        for one_service in services:
            print("Got service:", one_service.epr)
            if one_service.epr == device_A_UUID.urn:
                print("Match found:", one_service)
                my_client = SdcConsumer.from_wsd_service(one_service, ssl_context_container=None)
                my_client.start_all(not_subscribed_actions=periodic_actions)
                my_mdib = ConsumerMdib(my_client)
                my_mdib.init_mdib()
                observableproperties.bind(my_mdib, metrics_by_handle=on_metric_update)
                found_device = True
                set_ensemble_context(my_mdib, my_client)

    # Start the TCP client in a separate thread if needed
    tcp_client_thread = threading.Thread(target=start_tcp_client, daemon=True)
    tcp_client_thread.start()

    # Run the plot animation
    ani = animation.FuncAnimation(fig, update_plot, init_func=init, blit=True, interval=100)
    plt.show()

    # Keep the client running to get notified on metric changes
    while True:
        time.sleep(1)
