import paho.mqtt.client as mqtt
import ssl
import logging
from bumper.mqtt.qos import QoS
from queue import Queue, Full, Empty


class MqttClient():
    def __init__(self,
                 address: tuple,
                 client_id: str,
                 certs: dict | None = None,
                 buffer_size: int = 0) -> None:
        self.__ip: str = address[0]
        self.__port: int = address[1]
        self.__client: mqtt.Client = \
            mqtt.Client(client_id=client_id,
                        callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        if certs is not None:
            self.__client.tls_set(
                ca_certs=certs.get("CA_CERT"),
                certfile=certs.get("CLIENT_CERT"),
                keyfile=certs.get("CLIENT_KEY"),
                tls_version=ssl.PROTOCOL_TLSv1_2,
                ciphers=None
            )
            self.__client.tls_insecure_set(True)
        self.__client.on_message = self.__on_message
        self.__client.enable_logger()
        self.__message_received: dict[str, Queue[str]] = {}
        self.__buffer_size = buffer_size

    def __on_message(self, client, userdata, msg) -> None:
        try:
            self.__message_received[msg.topic].put_nowait(msg.payload.decode())
        except Full:
            logging.error(f"Queue on topic {msg.topic} is full")

    def connect(self) -> None:
        try:
            self.__client.connect(self.__ip, self.__port, keepalive=60)
            self.__client.loop_start()
        except Exception as error:
            logging.error(f"Connection failed: {error}")
            raise IOError(error)

    def publish(self, topic: str, payload: str, qos: QoS = QoS.QoS0) -> None:
        try:
            self.__client.publish(topic, payload, qos.value)
        except Exception as error:
            logging.error(f"Publish failed: {error}")
            raise IOError(error)

    def subscribe(self, topic: str, qos: QoS) -> None:
        try:
            self.__client.subscribe(topic, qos=qos.value)
            topic_queue: Queue = Queue(maxsize=self.__buffer_size)
            self.__message_received[topic] = topic_queue
        except Exception as error:
            logging.error(f"Subscribe failed: {error}")
            raise IOError(error)

    def disconnect(self) -> None:
        self.__client.loop_stop()
        self.__client.disconnect()

    def get_received_messages_no_wait(self, topic: str) -> str | None:
        try:
            result: str | None = self.__message_received[topic].get_nowait()
            return result
        except Empty:
            logging.error(f"Queue on topic {topic} is empty")
            raise Empty
        except KeyError:
            logging.error(f"Topic {topic} is not subscribed yet")
            raise KeyError

    def get_received_messages(self, topic) -> str | None:
        try:
            result: str | None = self.__message_received[topic].get()
            return result
        except KeyError:
            logging.error(f"Topic {topic} is not subscribed yet")
            raise KeyError
