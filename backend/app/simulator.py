"""Hardware simulator for Lock&Go lockers.

This script simulates the ESP32 hardware behavior, allowing testing
without physical hardware. It listens for OPEN commands and simulates
the lock mechanism.
"""

import asyncio
import aiomqtt
import os

MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
COMMAND_TOPIC_PATTERN = "lockngo/+/command"


async def simulate_hardware():
    """
    Simulates ESP32 hardware behavior:
    - Listens for OPEN commands on lockngo/+/command
    - Simulates lock opening (2 second delay)
    - Publishes READY status back to lockngo/{id}/status
    """
    print(f"🔧 [SIMULATOR] Starting Hardware Simulator...")
    print(f"🔧 [SIMULATOR] Connecting to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
    
    while True:
        try:
            async with aiomqtt.Client(MQTT_BROKER, port=MQTT_PORT) as client:
                print("✅ [SIMULATOR] Connected to MQTT Broker")
                await client.subscribe(COMMAND_TOPIC_PATTERN)
                print(f"📡 [SIMULATOR] Subscribed to: {COMMAND_TOPIC_PATTERN}")
                print("🔧 [SIMULATOR] Ready to simulate lock operations...")
                
                async for message in client.messages:
                    payload = message.payload.decode()
                    topic = message.topic.value
                    
                    # Extract locker ID from topic (format: lockngo/{id}/command)
                    parts = topic.split("/")
                    if len(parts) >= 2:
                        locker_id = parts[1]
                    else:
                        locker_id = "unknown"
                    
                    # Only process OPEN commands
                    if payload.strip().upper() == "OPEN":
                        print(f"🔓 [SIMULATOR] Physical Lock {locker_id} UNLOCKED via Relay!")
                        
                        # Simulate lock opening duration (2 seconds)
                        await asyncio.sleep(2)
                        
                        print(f"🔒 [SIMULATOR] Physical Lock {locker_id} auto-locked.")
                        
                        # Publish READY status back
                        status_topic = f"lockngo/{locker_id}/status"
                        try:
                            await client.publish(status_topic, "READY")
                            print(f"📤 [SIMULATOR] Published status 'READY' to {status_topic}")
                        except Exception as e:
                            print(f"⚠️ [SIMULATOR] Failed to publish status: {e}")
                    else:
                        print(f"ℹ️ [SIMULATOR] Received non-OPEN command: {payload} on {topic}")
                        
        except aiomqtt.MqttError as e:
            print(f"⚠️ [SIMULATOR] MQTT Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ [SIMULATOR] Critical Error: {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    # Allow running the simulator as a standalone script
    asyncio.run(simulate_hardware())


