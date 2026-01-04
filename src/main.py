import sunspec2.modbus.client as client
import time
import json
from paho.mqtt.enums import CallbackAPIVersion
import paho.mqtt.client as mqtt

TOPIC_PREFIX = 'FranklinWH'

EXCLUDE_KEYS = {'ID', 'MnAlrmInfo'}

INCLUDE_MODELS = {
    701: 'DERMeasureAC',
    713: 'DERStorageCapacity',
    714: 'DERMeasureDC',
    502: 'SolarModule'
}

def get_secrets() -> dict:
    with open('./secrets.json', 'r') as secrets:
        return json.load(secrets)

class Agate:
    
    def __init__(
        self, 
        ip_addr: str,
        ip_port: int,
        mqtt_user=None,
        mqtt_pass=None,
        mqtt_port=None,
        mqtt_host=None,
        mqtt_client_id='FranklinWH',
        sleep=30,
    ) -> None:
        self._client = client.SunSpecModbusClientDeviceTCP(
            slave_id=1,
            ipaddr=ip_addr,
            ipport=ip_port
        )
        self._sleep = sleep
        self._mqtt_user=mqtt_user
        self._mqtt_pass=mqtt_pass
        self._mqtt_host=mqtt_host
        self._mqtt_port=mqtt_port
        self._mqtt_client_id=mqtt_client_id

    def get_dict(self) -> dict:
        self._client.scan()
        values: dict = self._client.get_dict()
        self._client.close()
        return values

    def read(self) -> None:
        self.models = dict()
        values = self.get_dict()
        for model in values['models']:
            self.models[model['ID']] = model
    
    def get_topic(self, key: str, value):
        if not isinstance(value, (float, int)):
            return
        return (key, value)

    def get_model_topics(self, model, prefix):
        for key, value in model.items():
            if not key in EXCLUDE_KEYS:
                topic: tuple[str, float | int] | None = self.get_topic(f"{TOPIC_PREFIX}/AGate/{prefix}/{key}", value)
                if topic is not None:
                    yield topic

    def publish_topics(self, topics: list[tuple[str, int | float]]) -> None:
        mqttc = mqtt.Client(client_id=self._mqtt_client_id, callback_api_version=CallbackAPIVersion.VERSION2)
        mqttc.username_pw_set(username=self._mqtt_user, password=self._mqtt_pass)
        print(f"Connecting to MQTT server {self._mqtt_host}:{self._mqtt_port}...")
        mqttc.connect(host=self._mqtt_host, port=self._mqtt_port)
        mqttc.loop_start()
        print(f"Publishing {len(topics)} MQTT Topics...")
        try:
            messages = []
            for topic, payload in topics:
                message = mqttc.publish(topic, payload, qos=1)
                messages.append(message)
            while messages:
                print(f"Waiting for {len(messages)} messages to complete...")
                filtered = []
                for message in messages:
                    if not message.is_published():
                        filtered.append(message)
                messages = filtered
                time.sleep(0.5)
        finally:
            print("Disconnecting from MQTT Server...")
            mqttc.disconnect()
            mqttc.loop_stop()

    def publish(self)-> None:
        topics: list[tuple[str, float | int]] = []
        for key, name in INCLUDE_MODELS.items():
            if key in self.models:
                for topic in self.get_model_topics(self.models[key], name):
                    topics.append(topic)
        self.publish_topics(topics)
        
    def poll(self) -> None:
        while True:
            print("Polling...")
            self.read()
            self.publish()
            print(f"Done polling! Sleeping for {self._sleep}s")
            time.sleep(self._sleep)

    def write_json(self) -> None:
        print("Writing json...")
        with open('./data/agate_dump.json', r'w') as outfile:
            json.dump(self.get_dict(), outfile, indent=4)

if __name__ == '__main__':
    secrets = get_secrets()
    agate = Agate(
        ip_addr=secrets['ip_addr'],
        ip_port=secrets['ip_port'],
        mqtt_user=secrets['mqtt_user'], 
        mqtt_pass=secrets['mqtt_pass'],
        mqtt_host=secrets['mqtt_host'],
        mqtt_port=secrets['mqtt_port'],
    )
    agate.poll()
