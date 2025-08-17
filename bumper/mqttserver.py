#!/usr/bin/env python3

import logging
import asyncio
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0
import time
import bumper
import json
from datetime import datetime, timedelta
import bumper
from passlib.apps import custom_app_context as pwd_context

helperbotlog = logging.getLogger("helperbot")
boterrorlog = logging.getLogger("boterror")
mqttserverlog = logging.getLogger("mqttserver")


class MQTTHelperBot:
    wait_resp_timeout_seconds = 10
    expire_msg_seconds = 10

    def __init__(self, address, id: str = "helperbot@bumper/helperbot"):
        self.Client = None
        self.address = address
        self.client_id = id
        self.command_responses = []

    async def start_helper_bot(self):
        try:
            if self.Client is None:
                self.Client = MQTTClient(
                    client_id=self.client_id, config={"check_hostname": False,
                                                      "reconnect_retries": 20}
                )

            await self.Client.connect(
                "mqtts://{}:{}/".format(self.address[0], self.address[1]),
                cafile=bumper.ca_cert,
            )
            await self.Client.subscribe(
                [
                    ("iot/p2p/+/+/+/+/helperbot/bumper/helperbot/+/+/+", QOS_0),
                    ("iot/p2p/+", QOS_0),
                    ("iot/atr/+", QOS_0),
                ]
            )


#        except ConnectionRefusedError as e:
#            helperbotlog.Error(e)
#            pass

#        except asyncio.CancelledError as e:
#            pass

#        except hbmqtt.client.ConnectException as e:
#            helperbotlog.Error(e)
#            pass

        except Exception as e:
            helperbotlog.exception("{}".format(e))

    async def message_handler(self):
        try:
            while True:
                message = await self.Client.deliver_message()
                packet = message.publish_packet

                msg_topic = message.topic
                msg_payload = packet.payload.data.decode()

                # Add the message to the response queue
                self.command_responses.append({
                    "topic": msg_topic,
                    "payload": msg_payload,
                })

        except asyncio.CancelledError:
            helperbotlog.debug("message_handler cancelled")
        except Exception as e:
            helperbotlog.exception("Exception in message_handler: {}".format(e))

    async def wait_for_resp(self, requestid):
        try:

            t_end = (
                datetime.now() + timedelta(seconds=self.wait_resp_timeout_seconds)
            ).timestamp()

            while time.time() < t_end:
                await asyncio.sleep(0.1)
                if len(self.command_responses) > 0:
                    for msg in self.command_responses:
                        topic = str(msg["topic"]).split("/")
                        if topic[6] == "helperbot" and topic[10] == requestid:
                            if topic[11] == "j":
                                resppayload = json.loads(msg["payload"])
                            else:
                                resppayload = str(msg["payload"])
                            resp = {"id": requestid, "ret": "ok", "resp": resppayload}
                            self.command_responses.remove(msg)
                            return resp

            return {
                "id": requestid,
                "errno": 500,
                "ret": "fail",
                "debug": "wait for response timed out",
            }
        except asyncio.CancelledError as e:
            helperbotlog.debug("wait_for_resp cancelled by asyncio")
            return {
                "id": requestid,
                "errno": 500,
                "ret": "fail",
                "debug": "wait for response timed out",
            }
        except Exception as e:
            helperbotlog.exception("{}".format(e))
            return {
                "id": requestid,
                "errno": 500,
                "ret": "fail",
                "debug": "wait for response timed out",
            }

    async def send_command(self, cmdjson, requestid):
        if not self.Client._handler.writer is None:
            try:
                ttopic = "iot/p2p/{}/helperbot/bumper/helperbot/{}/{}/{}/q/{}/{}".format(
                    cmdjson["cmdName"],
                    cmdjson["toId"],
                    cmdjson["toType"],
                    cmdjson["toRes"],
                    requestid,
                    cmdjson["payloadType"],
                )
                try:
                    if cmdjson["payloadType"] == "x":
                        await self.Client.publish(
                            ttopic, str(cmdjson["payload"]).encode(), QOS_0
                        )

                    if cmdjson["payloadType"] == "j":
                        await self.Client.publish(
                            ttopic, json.dumps(cmdjson["payload"]).encode(), QOS_0
                        )

                except Exception as e:
                    helperbotlog.exception("{}".format(e))

                resp = await self.wait_for_resp(requestid)

                return resp

            except Exception as e:
                helperbotlog.exception("{}".format(e))
                return {}

    async def getResponse(self) -> list:
        return self.command_responses

    async def startListener(self) -> None:
        if not hasattr(self, "_message_handler_task"):
            self._message_handler_task = asyncio.create_task(self.message_handler())

    async def subscribe_to_topic(self, topic:str) -> None:
        await self.Client.subscribe(
                    [
                        (topic, QOS_0)
                    ]
                )