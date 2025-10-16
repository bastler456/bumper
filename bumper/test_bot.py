import time
import paho.mqtt.client as mqtt
import ssl

BROKER = '127.0.1.1'        # Change this to your broker's IP/domain
PORT = 8883                # Default MQTT port
TOPIC = 'test/bumper'       # Topic to publish/subscribe
TEST_MESSAGE = 'MQTT BUMP TEST'
CLIENT_ID = 'mqtt_bumper_tester'
CA_CERT = "certs/ca.crt"     # Path to your CA certificate file
# Optional (if client cert auth is needed)
CLIENT_CERT = "certs/bumper.crt" # e.g. '/path/to/client.crt'
CLIENT_KEY = "certs/bumper.key"   # e.g. '/path/to/client.key'

# This flag helps us confirm receipt of our own message
message_received = False

# Callback when client receives a CONNACK response from the server
def on_connect(client, userdata, flags, rc, hello):
    if rc == 0:
        print("✅ Connected to broker")
        client.subscribe(TOPIC)
        print(f"📡 Subscribed to topic: {TOPIC}")
        client.publish(TOPIC, TEST_MESSAGE)
        print(f"📤 Published test message: {TEST_MESSAGE}")
    else:
        print(f"❌ Connection failed with code {rc}")

# Callback when a PUBLISH message is received from the server
def on_message(client, userdata, msg):
    global message_received
    payload = msg.payload.decode()
    print(f"📥 Received message: {payload} on topic: {msg.topic}")
    if payload == TEST_MESSAGE:
        message_received = True

def main():
    global message_received
    client = mqtt.Client(client_id=CLIENT_ID, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    client.tls_set(
        ca_certs=CA_CERT,
        certfile=CLIENT_CERT,
        keyfile=CLIENT_KEY,
        tls_version=ssl.PROTOCOL_TLSv1_2,
        ciphers=None
    )

    client.tls_insecure_set(True)

    try:
        client.connect(BROKER, PORT, keepalive=60)
    except Exception as e:
        print(f"❌ Could not connect to MQTT broker: {e}")
        return
    
    print("✅ Connected to broker")
    client.subscribe(TOPIC)
    print(f"📡 Subscribed to topic: {TOPIC}")
    client.publish(TOPIC, "message_to_send")
    print("📤 Published message: {message_to_send}")

    client.loop_start()

    # Wait for message or timeout
    timeout = 5  # seconds
    start_time = time.time()
    while time.time() - start_time < timeout:
        if message_received:
            print("✅ MQTT server is running and message loopback confirmed!")
            break
        time.sleep(0.1)
    else:
        print("⚠️ Test failed: Did not receive loopback message in time.")

    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    main()