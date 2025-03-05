"""
Berryble - WiFi connect via BLE

This module implements a BLE peripheral device that provides a UART service,
allowing for bidirectional communication over BLE, aimed at setting up WiFi
connections for a headless Raspberry Pi.

Adding more commands is pretty straightforward.
"""

import subprocess
import json
import traceback
import socket

from gi.repository import GLib

# Bluezero modules
from bluezero import adapter
from bluezero import peripheral
from bluezero import device

# Nordic UART Service (NUS) UUIDs
UART_SERVICE = '6E400001-B5A3-F393-E0A9-E50E24DCCA9E'
RX_CHARACTERISTIC = '6E400002-B5A3-F393-E0A9-E50E24DCCA9E'
TX_CHARACTERISTIC = '6E400003-B5A3-F393-E0A9-E50E24DCCA9E'

ap_list = []

class UARTDevice:
    """
    Implements a BLE UART device with command handling capabilities.
    
    This class manages the BLE UART service, handling connections,
    disconnections, and data transfer between the BLE device and host.
    """
    
    tx_obj = None  # Holds the TX characteristic object for sending responses

    @classmethod
    def on_connect(cls, ble_device: device.Device):
        """Called when a BLE device connects."""
        print("Connected to " + str(ble_device.address))

    @classmethod
    def on_disconnect(cls, adapter_address, device_address):
        """Called when a BLE device disconnects."""
        print("Disconnected from " + device_address)

    @classmethod
    def uart_notify(cls, notifying, characteristic):
        """
        Handles notification state changes for the TX characteristic.
        
        Args:
            notifying: Boolean indicating if notifications are enabled
            characteristic: The TX characteristic object
        """
        if notifying:
            cls.tx_obj = characteristic
        else:
            cls.tx_obj = None

    @classmethod
    def update_tx(cls, value):
        """
        Processes received data and sends response through TX characteristic.
        
        Args:
            value: Received data to be processed
        """
        if cls.tx_obj:
            run_cmd(value.decode(), cls.tx_obj)

    @classmethod
    def uart_write(cls, value, options):
        """
        Handles data written to the RX characteristic.
        
        Args:
            value: Data received from the client
            options: Write options (unused)
        """
        cls.update_tx(value)


def nmcli_multiline_to_json(msg):
    """
    Converts nmcli multiline output to a list of dictionaries.
    
    Args:
        msg: Multiline string output from nmcli command
        
    Returns:
        List of dictionaries containing parsed network information
    """
    res = list()
    item = dict()
    for raw_line in msg.split("\n"):
        line = raw_line.strip()
        if line != "":
            parts = line.split(":", 1)
            if len(parts) >= 2:
                name = parts[0].strip()
                value = parts[1].strip()
                if name in item:
                    res.append(item)
                    item = dict()
                item[name] = value
    if len(item) > 0:
        res.append(item)
    return res

def parse_cmd(cmd: str) -> list[str]:
    res: list[str] = []
    # state machine
    st_init = 0
    st_token = 1
    st_wait_quote = 2
    st_escape_plain = 3
    st_escape_quoted = 4
    state = st_init
    token = ""
    for c in cmd:
        if state == st_init:
            if c.isspace():
                pass
            elif c == "\"":
                state = st_wait_quote
            elif c == "\\":
                state = st_escape_plain
            else:
                token += c
                state = st_token
        elif state == st_wait_quote:
            if c == "\"":
                res.append(token)
                token = ""
                state = st_init
            elif c == "\\":
                state = st_escape_quoted
            else:
                token += c
        elif state == st_escape_plain:
            token += c
            state = st_token
        elif state == st_escape_quoted:
            token += c
            state = st_wait_quote
        elif state == st_token:
            if c == "\\":
                state = st_escape_plain
            elif c.isspace():
                res.append(token)
                token = ""
                state = st_token
            else:
                token += c
        else:
            raise Exception(f"internal error, invalid state: {state}")
    if state == st_init:
        pass
    elif state == st_token:
        res.append(token)
    elif state == st_wait_quote:
        raise Exception("unclosed double quote")
    elif state == st_escape_plain:
        raise Exception("unexpected token end")
    elif state == st_escape_quoted:
        raise Exception("unexpected token end")
    else:
        raise Exception(f"internal error, invalid state: {state}")
    return res


def run_cmd(cmd_str, char):
    """
    Executes WiFi-related commands and sends responses via BLE.
        
    Args:
        cmd: Command string to execute
        char: TX characteristic for sending responses
    """
    global ap_list

    try:
        parts = parse_cmd(cmd_str)
        if len(parts) == 0:
            return
        cmd = parts[0].lower()
        if cmd in ["h", "help"]:
            returncode, msg = 0, "\n".join([
                "s|scan: start background wifi scan",
                "l|list: list available networks",
                "c|conn <ssid>|<index> [<passwd>]: connect to a network",
                "a|addr: list IP addresses",
                "on: turn on wifi",
                "off: turn off wifi",
                "r|reboot: reboot device",
                "p|poweroff: poweroff device",
            ])
        elif cmd in ["s", "scan"]:
            # Trigger a new WiFi scan
            res = subprocess.run(
                ["nmcli", "device", "wifi", "rescan"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode, msg = res.returncode, res.stdout
        elif cmd in ["l", "list"]:
            # List available WiFi networks with details
            res = subprocess.run(
                ["nmcli", "-m", "multiline", "-f", "BSSID,SSID,SECURITY,SIGNAL,IN-USE,CHAN", "device", "wifi", "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode = res.returncode
            msg = res.stdout
            if returncode == 0:
                msg = "SSID (BSSID) SECURITY SIGNAL (CHANNEL)"
                ap_list = nmcli_multiline_to_json(res.stdout) 
                for i, t in enumerate(ap_list):
                    msg += f'\n{i}) {t["IN-USE"]}{t["SSID"]} ({t["BSSID"]}) {t["SECURITY"]} {t["SIGNAL"]} ({t["CHAN"]})'
        elif cmd in ["c", "conn"]:
            # Connect to specified WiFi network
            if len(parts) < 2:
                returncode, msg = 1, "bad format"
            else:
                # either use the ap name directly or the index to the ap from the last list command
                ap_name = parts[1]
                ap_bssid = None
                try:
                    idx = int(parts[1])
                    if idx >= 0 and idx < len(ap_list):
                        ap_name = ap_list[idx]['SSID']
                        ap_bssid = ap_list[idx]['BSSID']
                except ValueError:
                    pass
                tcmd = ["nmcli", "device", "wifi", "connect", ap_name]
                # using the index is the way to connect to a specific BSSID
                if ap_bssid is not None:
                    tcmd.extend(["bssid", ap_bssid])
                if len(parts) > 2:
                    tcmd.extend(["password", parts[2]])
                res = subprocess.run(
                    tcmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                returncode = res.returncode
                msg = res.stdout
        elif cmd in ["a", "addr"]:
            res = subprocess.run(
                ["ip", "-j", "a"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode = res.returncode
            msg = res.stdout
            if returncode == 0:
                data = None
                try:
                    data = json.loads(res.stdout)
                except ValueError:
                    pass
                if data is not None:
                    msg2 = ""
                    for d in data:
                        try:
                            if d["operstate"] != "DOWN" and len(d["addr_info"]) > 0:
                                msg2 += "\n" if len(msg) > 0 else ""
                                msg2 += f'{d["ifname"]} {", ".join([a["local"] for a in d["addr_info"]])}'
                        except KeyError:
                            msg2 = ""
                            break
                    if msg2 != "":
                        msg = msg2
        elif cmd in ["off"]:
            # turn off wifi
            res = subprocess.run(
                ["nmcli", "radio", "wifi", "off"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode, msg = res.returncode, res.stdout
        elif cmd in ["on"]:
            # turn on wifi
            res = subprocess.run(
                ["nmcli", "radio", "wifi", "on"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode, msg = res.returncode, res.stdout
        elif cmd in ["r", "reboot"]:
            res = subprocess.run(
                ["sudo", "reboot"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode, msg = res.returncode, res.stdout
        elif cmd in ["p", "poweroff"]:
            res = subprocess.run(
                ["sudo", "poweroff"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            returncode, msg = res.returncode, res.stdout
        else:
            returncode = 1
            msg = "unknown command"

        # Format and send response in chunks (BLE has packet size limitations)
        output = f"code: {returncode}"
        if len(msg) > 0:
            output += f"\n{msg}"
        output_parts = []
        while len(output) > 500:
            output_parts.append(output[:500])
            output = output[500:]
        if len(output) > 0:
            output_parts.append(output)
        for p in output_parts:
            char.set_value(p.encode())
    except Exception:
        print(traceback.format_exc())
        raise


def main(adapter_address):
    """
    Sets up and starts the BLE UART service.
    
    Args:
        adapter_address: Bluetooth adapter address to use
    """
    # Initialize BLE peripheral with UART service
    ble_uart = peripheral.Peripheral(adapter_address, local_name=socket.gethostname())
    
    # Add UART service with RX and TX characteristics
    ble_uart.add_service(srv_id=1, uuid=UART_SERVICE, primary=True)
    
    # RX characteristic - for receiving commands
    ble_uart.add_characteristic(srv_id=1, chr_id=1, uuid=RX_CHARACTERISTIC,
                                value=[], notifying=False,
                                flags=['write', 'write-without-response', 'encrypt-authenticated-write'],
                                write_callback=UARTDevice.uart_write,
                                read_callback=None,
                                notify_callback=None)
    
    # TX characteristic - for sending responses
    ble_uart.add_characteristic(srv_id=1, chr_id=2, uuid=TX_CHARACTERISTIC,
                                value=[], notifying=False,
                                flags=['notify', 'encrypt-authenticated-read'],
                                notify_callback=UARTDevice.uart_notify,
                                read_callback=None,
                                write_callback=None)
    
    # Set connection callbacks
    ble_uart.on_connect = UARTDevice.on_connect
    ble_uart.on_disconnect = UARTDevice.on_disconnect

    # Start advertising the service
    ble_uart.publish()


if __name__ == '__main__':
    # Start the service using the first available Bluetooth adapter
    main(list(adapter.Adapter.available())[0].address)
