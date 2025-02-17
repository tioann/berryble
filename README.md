# berryble

WiFi configuration for a headless Raspberry Pi has never been easier! Use your BLE-enabled mobile phone to connect your Raspberry Pi to any network without any additional hardware.

A main goal for this project was to develop a working solution with the least amount of effort. Most of the code was built using [codebuff](https://www.codebuff.com) on a Raspberry Pi :-).

## prerequisites

- a recent raspi OS (debian bookworm)
- a Raspberry Pi with bluetooth support
- `nRF Toolbox` installed on the mobile phone
- Raspberry Pi desktop access for pairing the mobile phone (or `bluetoothctl` for systems without a desktop, untested)

## initial setup

- checkout the project locally
- run `./install.sh` to create and start the BLE service
- install `nRF Toolbox` on your mobile phone
- open `nRF Toolbox` and select `UART` under `Utils services`
- select the bluetooth device (by default the name is the Raspberry Pi hostname)
- IMPORTANT: make sure the phone is paired with the device on first connect, the BLE service as configured requires an encrypted connection

## usage

- open `nRF Toolbox` and select `UART` under `Utils services`
- select the bluetooth device
- once the connection is established, type `help` at the prompt to list available commands:
  - `help`: Show available commands
  - `scan`: Start background wifi scan
  - `list`: List available networks
  - `conn <ssid> [<passwd>]`: Connect to a network
- all (almost) commands correspond to a cli command, the output consists of a line for displaying the command return code followed by the actual command output

## issues

Setting up bluetooth pairing and communications can be a bit frustrating at times. For example:

- Initial pairing can fail with either the Raspberry Pi or the android phone getting "stuck" during the process. Solved by repeating the process a few times.
- The `nRF Toolbox` fails to establish a connection after selecting the peer, with either being stuck waiting for connection or outright showing connection failure. Sometimes, after 10 to 15 seconds the connection is suddenly established and the console shown. Solved by exiting and reentering the app a few times, also by dropping the app from the background apps and relaunching.
- Console shown but no response received on entering commands. This is normal when running a command such as `list` or `conn`, it takes several seconds for the results to show up. In very few cases where the response is never received even after waiting for a minute restarting the application seems to fix it. This is pretty rare.

In general, please be a bit patient, ensure that the device is showing up as paired and connected by the phone and restart the `nRF Toolbox` application. Give it enough time to scan for the bluetooth devices and on the waiting connection/not connected screens. These could be issues with my particular phone and may not be an issue for you.
