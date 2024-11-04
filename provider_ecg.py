from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
import math  # Used for generating a simple ECG-like waveform

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

    my_discovery = WSDiscoverySingleAdapter("Loopback Pseudo-Interface 1")
    my_discovery.start()
    my_mdib = ProviderMdib.from_mdib_file("mdib.xml")
    print("My UUID is {}".format(my_uuid))

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

    # Find or create the ECG metric
    ecg_metric_descrs = [c for c in my_mdib.descriptions.objects if c.NODETYPE == pm.NumericMetricDescriptor]
    with my_mdib.metric_state_transaction() as transaction_mgr:
        for metric_descr in ecg_metric_descrs:
            st = transaction_mgr.get_state(metric_descr.Handle)
            st.mk_metric_value()
            st.MetricValue.Validity = pm_types.MeasurementValidity.VALID
            st.ActivationState = pm_types.ComponentActivation.ON

    # Simulate ECG wave values (e.g., sine wave for demonstration)
    ecg_frequency = 1  # Frequency in Hertz for ECG simulation
    ecg_amplitude = Decimal(1.0)  # Placeholder amplitude

    # Infinite loop to send ECG data
    start_time = time.time()
    while True:
        elapsed_time = time.time() - start_time
        # Generate a simulated ECG value based on a sine function
        ecg_value = Decimal(ecg_amplitude * Decimal(math.sin(2 * math.pi * ecg_frequency * elapsed_time)))
        
        # Update the ECG metric in the MDIB
        with my_mdib.metric_state_transaction() as transaction_mgr:
            for metric_descr in ecg_metric_descrs:
                st = transaction_mgr.get_state(metric_descr.Handle)
                st.MetricValue.Value = ecg_value
        print(f"Sent ECG value: {ecg_value}")
        
        # Delay to simulate real-time ECG sending
        time.sleep(0.2)  # Adjust as needed for data frequency
