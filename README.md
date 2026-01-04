# FranklinWH Agate Minimal MQTT Publisher

- read values from sunspec modbus endpoint on Agate
- publish values to MQTT server

## Setup

Create a `secrets.json` file:

```json
{
    "mqtt_user": "<MQTT_NAME>",
    "mqtt_pass": "<MQTT_PASS>",
    "mqtt_host": "<MQTT_IP>",
    "mqtt_port": 1883, // example
    "ip_addr": "<AGATE_IP>",
    "ip_port": 502 // example
}
```

Install + run script

```
pip install -r ./requirements.txt
python3 ./src/main.py
```