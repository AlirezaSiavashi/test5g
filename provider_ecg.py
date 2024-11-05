from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
import math
import socket
import threading  # To handle multiple connections if needed

from sdc11073.location import SdcLocation
from sdc11073.loghelper import basic_logging_setup
from sdc11073.mdib import ProviderMdib
from sdc11073.provider import SdcProvider
from sdc11073.provider.components import SdcProviderComponents
from sdc11073.roles.product import ExtendedProduct
from sdc11073.wsdiscovery import WSDiscoverySingleAdapter
from sdc11073.xml_types import pm_qnames as pm
from sdc11073.xml_types import pm_types
from sdc11073.xml_types.dpws_types import ThisDeviceType
from sdc11073.xml_types.dpws_types import ThisModelType

# UUID setup
base_uuid = uuid.UUID('{cc013678-79f6-403c-998f-3cc0cc050230}')
my_uuid = uuid.uuid5(base_uuid, "12345")

# TCP server setup for communication with consumer
HOST = '127.0.0.1'  # Localhost for local machine communication
PORT = 65432        # Port for sending ECG data

clients = []  # List to hold connected clients

def start_tcp_server():
    """Start the TCP server to send ECG data to clients."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"Server listening on {HOST}:{PORT}")

    while True:
        client_socket, client_address = server_socket.accept()
        print(f"Connected by {client_address}")
        clients.append(client_socket)

def broadcast_data(data: str):
    """Send data to all connected clients."""
    for client in clients[:]:  # Iterate over a copy of the list
        try:
            client.sendall(data.encode())  # Send data as bytes
        except (BrokenPipeError, ConnectionResetError):
            clients.remove(client)  # Remove client if the connection is broken

def set_local_ensemble_context(mdib: ProviderMdib, ensemble_extension_string: str):
    descriptor_container = mdib.descriptions.NODETYPE.get_one(pm.EnsembleContextDescriptor)
    if not descriptor_container:
        print("No ensemble contexts in mdib")
        return
    all_ensemble_context_states = mdib.context_states.descriptor_handle.get(descriptor_container.Handle, [])
    with mdib.context_state_transaction() as mgr:
        associated_ensemble_context_states = [l for l in all_ensemble_context_states if
                                              l.ContextAssociation == pm_types.ContextAssociation.ASSOCIATED]
        for tmp in associated_ensemble_context_states:
            ensemble_context_state = mgr.get_context_state(tmp.DescriptorHandle, tmp.Handle)
            ensemble_context_state.ContextAssociation = pm_types.ContextAssociation.DISASSOCIATED
            ensemble_context_state.UnbindingMdibVersion = mdib.mdib_version

        new_ensemble_context_state = mgr.mk_context_state(descriptor_container.Handle, set_associated=True)
        new_ensemble_context_state.Identification = [
            pm_types.InstanceIdentifier(root="1.2.3", extension_string=ensemble_extension_string)]

if __name__ == '__main__':
    # Logging setup
    basic_logging_setup(level=logging.INFO)

    # Start the TCP server in a separate thread
    threading.Thread(target=start_tcp_server, daemon=True).start()

    # WS-Discovery for local machine communication
    my_discovery = WSDiscoverySingleAdapter("lo")
    my_discovery.start()
    my_mdib = ProviderMdib.from_mdib_file("mdib.xml")
    print("My UUID is {}".format(my_uuid))

    # Device and Model setup
    my_location = SdcLocation(fac='HOSP', poc='CU2', bed='BedSim')
    dpws_model = ThisModelType(manufacturer='Draeger',
                               manufacturer_url='www.draeger.com',
                               model_name='TestDevice',
                               model_number='1.0',
                               model_url='www.draeger.com/model',
                               presentation_url='www.draeger.com/model/presentation')
    dpws_device = ThisDeviceType(friendly_name='TestDevice',
                                 firmware_version='Version1',
                                 serial_number='12345')

    specific_components = SdcProviderComponents(role_provider_class=ExtendedProduct)
    sdc_provider = SdcProvider(ws_discovery=my_discovery,
                               epr=my_uuid,
                               this_model=dpws_model,
                               this_device=dpws_device,
                               device_mdib_container=my_mdib,
                               specific_components=specific_components
                               )
    sdc_provider.start_all()
    set_local_ensemble_context(my_mdib, "MyEnsemble")
    sdc_provider.set_location(my_location)

    # Configure ECG metric descriptors and initial values
    ecg_metric_descrs = [c for c in my_mdib.descriptions.objects if c.NODETYPE == pm.NumericMetricDescriptor]
    with my_mdib.metric_state_transaction() as transaction_mgr:
        for metric_descr in ecg_metric_descrs:
            st = transaction_mgr.get_state(metric_descr.Handle)
            st.mk_metric_value()
            st.MetricValue.Validity = pm_types.MeasurementValidity.VALID
            st.ActivationState = pm_types.ComponentActivation.ON

    # Simulate ECG wave values
    ecg_frequency = 1  # Frequency in Hertz
    ecg_amplitude = Decimal(1.0)  # Amplitude

    start_time = time.time()
    while True:
        elapsed_time = time.time() - start_time
        ecg_value = Decimal(ecg_amplitude * Decimal(math.sin(2 * math.pi * ecg_frequency * elapsed_time)))
        
        # Update the ECG metric in the MDIB
        with my_mdib.metric_state_transaction() as transaction_mgr:
            for metric_descr in ecg_metric_descrs:
                st = transaction_mgr.get_state(metric_descr.Handle)
                st.MetricValue.Value = ecg_value
        
        # Convert ECG value to string and broadcast to clients
        ecg_data = f"ECG Value: {ecg_value}\n"
        broadcast_data(ecg_data)
        
        print(f"Sent ECG value: {ecg_value}")
        
        # Delay to simulate real-time ECG data sending
        time.sleep(0.2)
