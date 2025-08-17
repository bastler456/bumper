import bumper
import pytest
import time
from bumper.mqtt.qos import QoS
import subprocess
import socket
from queue import Empty


def wait_for_mqtt(host: str, port: int, timeout: int = 10):
    """Wait for the MQTT broker to be available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(f"MQTT broker not available at {host}:{port}")


@pytest.fixture(scope="session")
def mosquitto_container():
    """Start Mosquitto using docker-compose before tests, stop after."""
    subprocess.run(["docker", "compose", "up", "-d", "mosquitto"], check=True)

    try:
        wait_for_mqtt("localhost", 1883)
    except TimeoutError:
        subprocess.run(["docker-compose", "logs", "mosquitto"])
        raise

    yield

    subprocess.run(["docker", "compose", "down"], check=True)


@pytest.fixture()
def certs() -> dict:
    certs: dict = {"CA_CERT": "certs/ca.crt",
                   "CLIENT_CERT": "certs/bumper.crt",
                   "CLIENT_KEY": "certs/bumper.key"}
    return certs


@pytest.mark.asyncio
async def test_mqtt_server_check_connection(certs, mosquitto_container):
    mqtt_address = ("127.0.0.1", 8883)
    client_id = "helperbot@bumper/helperbot"
    mqtt_client = bumper.MqttClient(mqtt_address, client_id, certs)
    mqtt_client.connect()
    mqtt_client.disconnect()
    assert True


def test_mqtt_server_send_receive_message(certs, mosquitto_container):
    mqtt_address = ("127.0.0.1", 8883)

    client_id = "helperbot@bumper/helperbot"
    mqtt_client_1 = bumper.MqttClient(mqtt_address, client_id, certs)
    mqtt_client_1.connect()

    msg_payload = "<ctl ts='1547822804960' td='DustCaseST' st='0'/>"

    msg_topic_name = "iot/atr/DustCaseST/bot_serial/ls1ok3/wC3g/x"
    mqtt_client_1.subscribe(msg_topic_name, QoS.QoS0)

    mqtt_client_1.publish(
        msg_topic_name, msg_payload, QoS.QoS0
    )
    time.sleep(0.1)
    response: str
    response = mqtt_client_1.get_received_messages(msg_topic_name)
    mqtt_client_1.disconnect()
    assert response == msg_payload


def test_mqtt_server_message_two_clients(certs, mosquitto_container):
    mqtt_address = ("127.0.0.1", 8883)

    client_id = "helperbot1@bumper/helperbot"
    mqtt_client_1 = bumper.MqttClient(mqtt_address, client_id, certs)
    mqtt_client_1.connect()
    client_id = "helperbot2@bumper/helperbot"
    mqtt_client_2 = bumper.MqttClient(mqtt_address, client_id, certs)
    mqtt_client_2.connect()

    msg_payload = "<ctl ts='1547822804960' td='DustCaseST' st='0'/>"

    msg_topic_name = "iot/atr/DustCaseST/bot_serial/ls1ok3/wC3g/x"
    mqtt_client_2.subscribe(msg_topic_name, QoS.QoS0)
    time.sleep(0.1)

    mqtt_client_1.publish(
        msg_topic_name, msg_payload, QoS.QoS0
    )
    time.sleep(0.1)
    response: str
    response = mqtt_client_2.get_received_messages(msg_topic_name)
    mqtt_client_1.disconnect()
    mqtt_client_2.disconnect()
    assert response == msg_payload


def test_client_get_received_message_nowait(certs, mosquitto_container):
    mqtt_address = ("127.0.0.1", 8883)
    client_id = "helperbot@bumper/helperbot"
    mqtt_client_1 = bumper.MqttClient(mqtt_address, client_id, certs)
    mqtt_client_1.connect()

    msg_topic_name = "iot/atr/DustCaseST/bot_serial/ls1ok3/wC3g/x"
    mqtt_client_1.subscribe(msg_topic_name, QoS.QoS0)

    with pytest.raises(Empty):
        mqtt_client_1.get_received_messages_no_wait(msg_topic_name)

    mqtt_client_1.disconnect()

def test_client_get_received_before_subscription(certs, mosquitto_container):
    mqtt_address = ("127.0.0.1", 8883)
    client_id = "helperbot@bumper/helperbot"
    mqtt_client_1 = bumper.MqttClient(mqtt_address, client_id, certs)
    mqtt_client_1.connect()

    msg_topic_name = "iot/atr/DustCaseST/bot_serial/ls1ok3/wC3g/x"

    with pytest.raises(KeyError):
        mqtt_client_1.get_received_messages(msg_topic_name)

    mqtt_client_1.disconnect()

