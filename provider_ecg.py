from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
import socket
import threading
import sqlite3
import os

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


# Network configuration
HOST = ''  # Replace with Provider Machine's IP
PORT = 65432             # Port for sending ECG data
DB_PATH = os.path.join("instance", "ecg_data.db")  # Path to the SQLite database in the 'instance' folder

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
    for client in clients[:]:
        try:
            client.sendall(data.encode())
        except (BrokenPipeError, ConnectionResetError):
            clients.remove(client)

def get_latest_ecg_data():
    """
    Fetch the latest ECG value from the database.
    Returns None if no data is available.
    """
    try:
        connection = sqlite3.connect(DB_PATH)
        cursor = connection.cursor()
        # Corrected table name to match your schema
        cursor.execute("SELECT adc_value FROM ecg_data ORDER BY timestamp DESC LIMIT 1;")
        result = cursor.fetchone()
        if result:
            return Decimal(result[0]) / Decimal(1000)  # Scale the value if needed
        else:
            print("No ECG data available in the database.")
            return None
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        connection.close()

def set_local_ensemble_context(mdib: ProviderMdib, ensemble_extension_string: str):
    """
    Manage and set a local ensemble context in the MDIB.
    """
    descriptor_container = mdib.descriptions.NODETYPE.get_one(pm.EnsembleContextDescriptor)
    if not descriptor_container:
        print("No ensemble contexts in MDIB")
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
    basic_logging_setup(level=logging.INFO)

    # Start the TCP server in a separate thread
    threading.Thread(target=start_tcp_server, daemon=True).start()

    # Setup SDC Provider
    my_discovery = WSDiscoverySingleAdapter("wlan0")  # Replace with your network adapter
    my_discovery.start()

    my_mdib = ProviderMdib.from_mdib_file("mdib.xml")

    my_uuid = uuid.uuid5(uuid.UUID('{cc013678-79f6-403c-998f-3cc0cc050230}'), "12345")
    print(f"My UUID is {my_uuid}")

    my_location = SdcLocation(fac='HOSP', poc='CU2', bed='BedSim')
    dpws_model = ThisModelType(manufacturer='Draeger',
                               model_name='TestDevice',
                               model_number='1.0')
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
    sdc_provider.set_location(my_location)

    # Set local ensemble context
    set_local_ensemble_context(my_mdib, "TestExtensionString")

    while True:
        # Fetch the latest ECG value from the database
        ecg_value = get_latest_ecg_data()

        if ecg_value is not None:
            # Update ECG Metric in MDIB
            with my_mdib.metric_state_transaction() as transaction_mgr:
                for metric_descr in my_mdib.descriptions.NODETYPE.get(pm.NumericMetricDescriptor, []):
                    st = transaction_mgr.get_state(metric_descr.Handle)
                    if st is None:
                        print(f"No state found for descriptor handle: {metric_descr.Handle}")
                        continue

                    # Check and initialize MetricValue if not set
                    if st.MetricValue is None:
                        print(f"Initializing MetricValue for {metric_descr.Handle}")
                        st.mk_metric_value()
                        st.MetricValue.Validity = pm_types.MeasurementValidity.VALID

                    # Set the ECG value
                    st.MetricValue.Value = ecg_value

            # Broadcast ECG data to clients
            ecg_data = f"ECG Value: {ecg_value}\n"
            broadcast_data(ecg_data)
            print(f"Sent ECG value: {ecg_value}")
        else:
            print("Skipping ECG update as no data was retrieved.")

        time.sleep(0.2)
