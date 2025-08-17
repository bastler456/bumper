import subprocess
import socket
import time
import pytest


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