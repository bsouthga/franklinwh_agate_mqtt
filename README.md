# FranklinWH Agate Minimal MQTT Publisher

- read values from sunspec modbus endpoint on Agate
- publish values to MQTT server

## Cli Parameters

```
usage: main.py [-h] --ip-addr IP_ADDR [--ip-port IP_PORT] --mqtt-host MQTT_HOST [--mqtt-port MQTT_PORT] [--mqtt-user MQTT_USER]
               [--mqtt-pass MQTT_PASS] [--client-id CLIENT_ID] [--sleep SLEEP] [--error-sleep ERROR_SLEEP] [--dump-json]

Read SunSpec data from a Modbus TCP device and publish it to MQTT.

options:
  -h, --help            show this help message and exit
  --ip-addr IP_ADDR     IP address of the SunSpec device
  --ip-port IP_PORT     TCP port of the SunSpec device (default: 502)
  --mqtt-host MQTT_HOST
                        Hostname / IP of the MQTT broker
  --mqtt-port MQTT_PORT
                        Port of the MQTT broker (default: 1883)
  --mqtt-user MQTT_USER
                        MQTT username (optional)
  --mqtt-pass MQTT_PASS
                        MQTT password (optional)
  --client-id CLIENT_ID
                        Client ID used when connecting to MQTT (default: FranklinWH)
  --sleep SLEEP         Normal polling interval in seconds (default: 30)
  --error-sleep ERROR_SLEEP
                        Sleep time after an error before retrying, in seconds (default: 60)
  --dump-json           If set, write a one‑off JSON dump of the raw SunSpec data to ./data/agate_dump.json
```

## Setup

Install + run script

```
pip install -r ./requirements.txt
python3 src/main.py \
    --ip-addr 192.168.1.100 \
    --ip-port 502 \
    --mqtt-host mqtt.example.com \
    --mqtt-port 1883 \
    --mqtt-user myuser \
    --mqtt-pass secret \
    --sleep 45 \
    --error-sleep 120
```