#!/usr/bin/env python3

from bumper.confserver import ConfServer
from bumper.xmppserver import XMPPServer
from bumper.mqtt.mqtt_client import MqttClient
from bumper.mqtt.qos import QoS
from bumper.models import *
from bumper.db import *
import asyncio
import os
import logging
from logging.handlers import RotatingFileHandler
import socket
import sys

import importlib
import pkgutil
from pkgutil import extend_path

def strtobool(strbool):
    if str(strbool).lower() in ["true", "1", "t", "y", "on", "yes"]:
        return True
    else:
        return False


# os.environ['PYTHONASYNCIODEBUG'] = '1' # Uncomment to enable ASYNCIODEBUG
bumper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

log_to_stdout = os.environ.get("LOG_TO_STDOUT")

# Set defaults from environment variables first
# Folders
if not log_to_stdout:
    logs_dir = os.environ.get("BUMPER_LOGS") or os.path.join(bumper_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)  # Ensure logs directory exists or create
data_dir = os.environ.get("BUMPER_DATA") or os.path.join(bumper_dir, "data")
os.makedirs(data_dir, exist_ok=True)  # Ensure data directory exists or create
certs_dir = os.environ.get("BUMPER_CERTS") or os.path.join(bumper_dir, "certs")
os.makedirs(certs_dir, exist_ok=True)  # Ensure data directory exists or create



# Certs
ca_cert:str = os.environ.get("BUMPER_CA") or os.path.join(certs_dir, "ca.crt")
server_cert:str = os.environ.get("BUMPER_CERT") or os.path.join(certs_dir, "bumper.crt")
server_key:str = os.environ.get("BUMPER_KEY") or os.path.join(certs_dir, "bumper.key")

certs: dict = {"CA_CERT": ca_cert,
               "CLIENT_CERT": server_cert,
               "CLIENT_KEY": server_key}

# Listeners
bumper_listen = os.environ.get("BUMPER_LISTEN") or socket.gethostbyname(
    socket.gethostname()
)


bumper_announce_ip = os.environ.get("BUMPER_ANNOUNCE_IP") or bumper_listen

# Other
bumper_debug = strtobool(os.environ.get("BUMPER_DEBUG")) or False
use_auth = False
token_validity_seconds = 3600  # 1 hour
oauth_validity_days = 15
db = None

mqtt_server = None
mqtt_helperbot = None
conf_server = None
conf_server_2 = None
xmpp_server = None

# Plugins
sys.path.append(os.path.join(bumper_dir, "bumper", "plugins"))
sys.path.append(os.path.join(data_dir, "plugins"))

discovered_plugins = {
    name: importlib.import_module(name)
    for finder, name, ispkg in pkgutil.iter_modules()
    if name.startswith('bumper_')
}

shutting_down = False

# Set format for all logs
logformat = logging.Formatter(
    "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(module)s :: %(funcName)s :: %(lineno)d :: %(message)s"
)

bumperlog = logging.getLogger("bumper")
if not log_to_stdout:
    bumper_rotate = RotatingFileHandler("logs/bumper.log", maxBytes=5000000, backupCount=5)
    bumper_rotate.setFormatter(logformat)
    bumperlog.addHandler(bumper_rotate)
else: 
    bumperlog.addHandler(logging.StreamHandler(sys.stdout))
# Override the logging level
# bumperlog.setLevel(logging.INFO)

confserverlog = logging.getLogger("confserver")
if not log_to_stdout:
    conf_rotate = RotatingFileHandler(
        "logs/confserver.log", maxBytes=5000000, backupCount=5
    )
    conf_rotate.setFormatter(logformat)
    confserverlog.addHandler(conf_rotate)
else:
    confserverlog.addHandler(logging.StreamHandler(sys.stdout))


# Override the logging level
# helperbotlog.setLevel(logging.INFO)

boterrorlog = logging.getLogger("boterror")
if not log_to_stdout:
    boterrorlog_rotate = RotatingFileHandler(
        "logs/boterror.log", maxBytes=5000000, backupCount=5
    )
    boterrorlog_rotate.setFormatter(logformat)
    boterrorlog.addHandler(boterrorlog_rotate)
else:
    boterrorlog.addHandler(logging.StreamHandler(sys.stdout))
# Override the logging level
# boterrorlog.setLevel(logging.INFO)

xmppserverlog = logging.getLogger("xmppserver")
if not log_to_stdout:
    xmpp_rotate = RotatingFileHandler(
        "logs/xmppserver.log", maxBytes=5000000, backupCount=5
    )
    xmpp_rotate.setFormatter(logformat)
    xmppserverlog.addHandler(xmpp_rotate)
else:
    xmppserverlog.addHandler(logging.StreamHandler(sys.stdout))
# Override the logging level
# xmppserverlog.setLevel(logging.INFO)

logging.getLogger("asyncio").setLevel(logging.CRITICAL + 1)  # Ignore this logger


mqtt_listen_port = 8883
conf1_listen_port = 443
conf2_listen_port = 8007
xmpp_listen_port = 5223


async def start():

    try:
        loop = asyncio.get_event_loop()
    except:
        loop = asyncio.new_event_loop()

    if bumper_debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(asctime)s] :: %(levelname)s :: %(name)s :: %(module)s :: %(funcName)s :: %(lineno)d :: %(message)s",
        )
        loop.set_debug(True)  # Set asyncio loop to debug
        # logging.getLogger("asyncio").setLevel(logging.DEBUG)  # Show debug asyncio logs (disabled in init, uncomment for debugging asyncio)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s",
        )

    if not bumper_listen:
        logging.log(logging.FATAL, "No listen address configured")
        return

    if not (
        os.path.exists(ca_cert)
        and os.path.exists(server_cert)
        and os.path.exists(server_key)
    ):
        logging.log(logging.FATAL, "Certificate(s) don't exist at paths specified")
        return

    bumperlog.info("Starting Bumper")
    global conf_server
    conf_server = ConfServer((bumper_listen, conf1_listen_port), usessl=True)
    # global conf_server_2
    # conf_server_2 = ConfServer((bumper_listen, conf2_listen_port), usessl=False)
    global xmpp_server
    xmpp_server = XMPPServer((bumper_listen, xmpp_listen_port))



    # Start XMPP Server
    asyncio.create_task(xmpp_server.start_async_server())


    # Start web servers
    conf_server.confserver_app(certs)
    # asyncio.create_task(conf_server.start_site(conf_server.app, address=bumper_listen, port=conf1_listen_port, usessl=True))
    asyncio.create_task(conf_server.start_site(conf_server.app, address=bumper_listen, port=conf2_listen_port, usessl=True))

    # Start maintenance
    while not shutting_down:
        asyncio.create_task(maintenance())
        await asyncio.sleep(5)


async def maintenance():
    revoke_expired_tokens()
    revoke_expired_oauths()


async def shutdown():
    try:
        bumperlog.info("Shutting down")
        await conf_server.stop_server()
        await conf_server_2.stop_server()
        if xmpp_server.server:
            if xmpp_server.server._serving:
                xmpp_server.server.close()
            await xmpp_server.server.wait_closed()
        global shutting_down
        shutting_down = True

    except asyncio.CancelledError:
        bumperlog.info("Coroutine canceled")

    except Exception as e:
        bumperlog.info("Exception: {}".format(e))

    finally:
        bumperlog.info("Shutdown complete")


def create_certs():
    import subprocess
    process = subprocess.Popen(
                                ["./create_certs/create_cert.sh"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
    )
    stdout, stderr = process.communicate()

    logging.debug(f"Creating Cert stdout = {stdout}",
                  f"stderr = {stderr}")

    if process.returncode == 0:
        print("Success:")
        print(stdout)
    else:
        print("Error:")
        print(stderr)

    print("Certificates created")

    if "__main__.py" in sys.argv[0]:
        os.execv(
            sys.executable, ["python", "-m", "bumper"] + sys.argv[1:]
        )  # Start again

    else:
        os.execv(sys.executable, ["python"] + sys.argv)  # Start again


def first_run():
    create_certs()


def main(argv=None):
    import argparse

    global bumper_debug
    global bumper_listen
    global bumper_announce_ip
    if not argv:
        argv = sys.argv[1:]  # Set argv to argv[1:] if not passed into main
    try:

        if not (
            os.path.exists(ca_cert)
            and os.path.exists(server_cert)
            and os.path.exists(server_key)
        ):
            first_run()
            return

        if not (
            os.path.exists(os.path.join(data_dir, "passwd"))
        ):
            with open(os.path.join(data_dir, "passwd"), 'w'): pass

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--listen", type=str, default=None, help="start serving on address"
        )
        parser.add_argument(
            "--announce",
            type=str,
            default=None,
            help="announce address to bots on checkin",
        )
        parser.add_argument("--debug", action="store_true", help="enable debug logs")

        args = parser.parse_args(args=argv)

        if args.debug:
            bumper_debug = True

        if args.listen:
            bumper_listen = args.listen

        if args.announce:
            bumper_announce_ip = args.announce

        asyncio.run(start())

    except KeyboardInterrupt:
        bumperlog.info("Keyboard Interrupt!")
        pass

    except Exception as e:
        bumperlog.exception(e)
        pass

    finally:
        asyncio.run(shutdown())

