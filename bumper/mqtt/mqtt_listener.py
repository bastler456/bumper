from bumper import MqttClient
import asyncio
import logging

class MqttListener():
    def __init__(self, mqtt_client: MqttClient):
        self.__mqtt_client: MqttClient = mqtt_client

    async def start_listener(self) -> None:
        try:
            while True:
                logging.debug("Listener task is running...")
                message = await self.__mqtt_client.get_received_messages()
        except asyncio.CancelledError:
            logging.debug("Listener task was cancelled.")

    @staticmethod
    async def __parse_message(message) -> None:
