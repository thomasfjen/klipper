# Report canbus connection status
#
# Copyright (C) 2025  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import logging

class PrinterCANBusStats:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.mcu = None
        self.get_canbus_status_cmd = None
        self.status = {'rx_error': None, 'tx_error': None, 'bus_state': None}
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.printer.register_event_handler("klippy:shutdown",
                                            self.handle_shutdown)
    def handle_shutdown(self):
        status = self.status.copy()
        if status['bus_state'] is not None:
            # Clear bus_state on shutdown to note that the values may be stale
            status['bus_state'] = 'unknown'
            self.status = status
    def handle_connect(self):
        # Lookup mcu
        mcu_name = self.name
        if mcu_name != 'mcu':
            mcu_name = 'mcu ' + mcu_name
        self.mcu = self.printer.lookup_object(mcu_name)
        # Lookup status query command
        if self.mcu.try_lookup_command("get_canbus_status") is None:
            return
        self.get_canbus_status_cmd = self.mcu.lookup_query_command(
            "get_canbus_status",
            "canbus_status rx_error=%u tx_error=%u canbus_bus_state=%u")
        # Register usb_canbus_state message handling (for usb to canbus bridge)
        self.mcu.register_response(self.handle_usb_canbus_state,
                                   "usb_canbus_state")
        # Register periodic query timer
        reactor = self.printer.get_reactor()
        reactor.register_timer(self.query_event, reactor.NOW)
    def handle_usb_canbus_state(self, params):
        discard = params['discard']
        if discard:
            logging.warning("USB CANBUS bridge '%s' is discarding!"
                            % (self.name,))
        else:
            logging.warning("USB CANBUS bridge '%s' is no longer discarding."
                            % (self.name,))
    def query_event(self, eventtime):
        prev_rx = self.status['rx_error']
        prev_tx = self.status['tx_error']
        if prev_rx is None:
            prev_rx = prev_tx = 0
        params = self.get_canbus_status_cmd.send()
        rx = prev_rx + ((params['rx_error'] - prev_rx) & 0xffffffff)
        tx = prev_tx + ((params['tx_error'] - prev_tx) & 0xffffffff)
        state = params['canbus_bus_state']
        self.status = {'rx_error': rx, 'tx_error': tx, 'bus_state': state}
        return eventtime + 1.
    def stats(self, eventtime):
        status = self.status
        if status['rx_error'] is None:
            return (False, '')
        return (False, 'canstat_%s: bus_state=%s rx_error=%d tx_error=%d'
                % (self.name, status['bus_state'],
                   status['rx_error'], status['tx_error']))
    def get_status(self, eventtime):
        return self.status

def load_config_prefix(config):
    return PrinterCANBusStats(config)
