import argparse
import json
import time
from pathlib import Path

import sunspec2.modbus.client as client
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

TOPIC_PREFIX = "FranklinWH"

EXCLUDE_KEYS = {"ID", "MnAlrmInfo"}

INCLUDE_MODELS = {
    701: "DERMeasureAC",
    713: "DERStorageCapacity",
    714: "DERMeasureDC",
    502: "SolarModule",
}


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    p = argparse.ArgumentParser(
        description="Read SunSpec data from a Modbus TCP device and publish it to MQTT."
    )
    p.add_argument("--ip-addr", required=True, help="IP address of the SunSpec device")
    p.add_argument(
        "--ip-port",
        type=int,
        default=502,
        help="TCP port of the SunSpec device (default: 502)",
    )
    p.add_argument("--mqtt-host", required=True, help="Hostname / IP of the MQTT broker")
    p.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="Port of the MQTT broker (default: 1883)",
    )
    p.add_argument("--mqtt-user", default=None, help="MQTT username (optional)")
    p.add_argument("--mqtt-pass", default=None, help="MQTT password (optional)")

    p.add_argument(
        "--client-id",
        default="FranklinWH",
        help="Client ID used when connecting to MQTT (default: FranklinWH)",
    )
    p.add_argument(
        "--sleep",
        type=int,
        default=30,
        help="Normal polling interval in seconds (default: 30)",
    )
    p.add_argument(
        "--error-sleep",
        type=int,
        default=60,
        help="Sleep time after an error before retrying, in seconds (default: 60)",
    )
    p.add_argument(
        "--dump-json",
        action="store_true",
        help="If set, write a one‑off JSON dump of the raw SunSpec data to ./data/agate_dump.json",
    )
    return p


class Agate:
    """
    Reads SunSpec registers from a Modbus/TCP device and publishes selected
    values to MQTT.
    """

    def __init__(
        self,
        ip_addr: str,
        ip_port: int,
        mqtt_host: str,
        mqtt_port: int,
        mqtt_user: str | None = None,
        mqtt_pass: str | None = None,
        mqtt_client_id: str = "FranklinWH",
        sleep: int = 30,
    ) -> None:
        # Modbus client (single‑shot – we open/close on every poll)
        self._client = client.SunSpecModbusClientDeviceTCP(
            slave_id=1, ipaddr=ip_addr, ipport=ip_port
        )
        self._sleep = sleep

        # MQTT connection details
        self._mqtt_user = mqtt_user
        self._mqtt_pass = mqtt_pass
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._mqtt_client_id = mqtt_client_id

    def get_dict(self) -> dict:
        """Scan the device and return the full SunSpec dictionary."""
        self._client.scan()
        values: dict = self._client.get_dict()
        self._client.close()
        return values

    def read(self) -> None:
        """Populate ``self.models`` with a mapping of model‑ID → model data."""
        self.models: dict[int, dict] = {}
        values = self.get_dict()
        for model in values["models"]:
            self.models[model["ID"]] = model

    @staticmethod
    def _maybe_topic(key: str, value):
        """Return a (topic, payload) tuple or ``None`` if the payload is not numeric."""
        if isinstance(value, (float, int)):
            return key, value
        return None

    def get_model_topics(self, model: dict, prefix: str):
        """
        Yield MQTT topic / payload pairs for a single SunSpec model,
        skipping keys listed in ``EXCLUDE_KEYS``.
        """
        for key, value in model.items():
            if key in EXCLUDE_KEYS:
                continue
            full_topic = f"{TOPIC_PREFIX}/AGate/{prefix}/{key}"
            maybe = self._maybe_topic(full_topic, value)
            if maybe is not None:
                yield maybe

    def publish_topics(self, topics: list[tuple[str, int | float]]) -> None:
        """Connect to the broker, publish all topics and wait for ACKs."""
        mqttc = mqtt.Client(
            client_id=self._mqtt_client_id,
            callback_api_version=CallbackAPIVersion.VERSION2,
        )
        if self._mqtt_user is not None or self._mqtt_pass is not None:
            mqttc.username_pw_set(username=self._mqtt_user, password=self._mqtt_pass)

        print(f"Connecting to MQTT broker {self._mqtt_host}:{self._mqtt_port} …")
        mqttc.connect(host=self._mqtt_host, port=self._mqtt_port)
        mqttc.loop_start()

        try:
            pending = []
            for topic, payload in topics:
                msg_info = mqttc.publish(topic, payload, qos=1)
                pending.append(msg_info)

            # Wait until every publish has been acknowledged (or failed)
            while pending:
                print(f"Waiting for {len(pending)} MQTT message(s) to complete …")
                still_pending = []
                for mi in pending:
                    if not mi.is_published():
                        still_pending.append(mi)
                pending = still_pending
                time.sleep(0.5)

        finally:
            print("Disconnecting from MQTT broker …")
            mqttc.disconnect()
            mqttc.loop_stop()

    def publish(self) -> None:
        """Collect topics for the models we care about and send them."""
        topics: list[tuple[str, int | float]] = []
        for model_id, name in INCLUDE_MODELS.items():
            if model_id in self.models:
                topics.extend(list(self.get_model_topics(self.models[model_id], name)))
        self.publish_topics(topics)

    def poll(self, error_sleep: int) -> None:
        """
        Run an infinite poll/publish cycle.

        Parameters
        ----------
        error_sleep: int
            Seconds to sleep after any exception before retrying.
        """
        while True:
            try:
                print("\n=== Poll start ===")
                self.read()
                self.publish()
                print(f"Poll completed – sleeping {self._sleep}s")
                time.sleep(self._sleep)

            except Exception as exc:  # pylint: disable=broad-except
                # Log the error, wait ``error_sleep`` seconds and continue.
                print(
                    f"\n*** ERROR while polling ***\n{type(exc).__name__}: {exc}\n"
                    f"Sleeping for {error_sleep}s before retry …"
                )
                time.sleep(error_sleep)

    def write_json(self) -> None:
        """Write a raw SunSpec dictionary to ./data/agate_dump.json."""
        out_path = Path("./data/agate_dump.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Writing JSON dump to {out_path} …")
        with out_path.open("w", encoding="utf-8") as outfile:
            json.dump(self.get_dict(), outfile, indent=4)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    # Build the Agate instance from CLI arguments
    agate = Agate(
        ip_addr=args.ip_addr,
        ip_port=args.ip_port,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_user=args.mqtt_user,
        mqtt_pass=args.mqtt_pass,
        mqtt_client_id=args.client_id,
        sleep=args.sleep,
    )

    # Optional one‑off JSON dump (useful for debugging / schema inspection)
    if args.dump_json:
        agate.write_json()
        return

    # Start the resilient poll loop
    agate.poll(error_sleep=args.error_sleep)


if __name__ == "__main__":
    main()
