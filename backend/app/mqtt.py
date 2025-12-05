import asyncio
import aiomqtt
import os
import re
from datetime import datetime, timezone

MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = 1883
TOPIC_PATTERN = "lockngo/+/status"

async def listen_mqtt():
    """
    Connects to MQTT broker and listens for status updates from lockers.
    Updates database with locker status and battery levels.
    Retries automatically on disconnection.
    """
    from .database import async_session_maker
    from .models import Locker, LockerStatus
    from sqlalchemy import select
    
    print(f"Attempting to connect to MQTT Broker at {MQTT_BROKER}...")
    while True:
        try:
            async with aiomqtt.Client(MQTT_BROKER, port=MQTT_PORT) as client:
                print("✅ Connected to MQTT Broker")
                await client.subscribe(TOPIC_PATTERN)
                
                async for message in client.messages:
                    payload = message.payload.decode()
                    topic = message.topic.value
                    
                    # Extract locker ID from topic: lockngo/locker_01/status
                    match = re.search(r'lockngo/(.+)/status', topic)
                    if not match:
                        print(f"⚠️ Invalid topic format: {topic}")
                        continue
                    
                    locker_mac = match.group(1)
                    print(f"📡 [{locker_mac}] Status: {payload}")
                    
                    # Update database
                    try:
                        async with async_session_maker() as session:
                            result = await session.execute(
                                select(Locker).where(Locker.mac_address == locker_mac)
                            )
                            locker = result.scalar_one_or_none()
                            
                            if locker:
                                updated = False
                                
                                # Handle different payload types
                                if payload == "OPENED":
                                    locker.status = LockerStatus.ACTIVE
                                    print(f"✅ Updated locker {locker_mac} status to ACTIVE")
                                    updated = True
                                    
                                elif payload == "CLOSED":
                                    locker.status = LockerStatus.ACTIVE
                                    print(f"✅ Locker {locker_mac} closed")
                                    updated = True
                                    
                                elif payload.isdigit():
                                    # Battery level (0-100)
                                    battery = int(payload)
                                    if 0 <= battery <= 100:
                                        locker.battery_level = battery
                                        print(f"🔋 Updated battery for {locker_mac}: {battery}%")
                                        
                                        # Update status based on battery
                                        if battery < 10:
                                            locker.status = LockerStatus.MAINTENANCE
                                            print(f"⚠️ Low battery alert for {locker_mac}")
                                        updated = True
                                
                                elif payload == "ERROR":
                                    locker.status = LockerStatus.BROKEN
                                    print(f"❌ Locker {locker_mac} reported error")
                                    updated = True
                                    
                                elif payload == "OFFLINE":
                                    locker.status = LockerStatus.OFFLINE
                                    print(f"⚠️ Locker {locker_mac} went offline")
                                    updated = True
                                
                                if updated:
                                    await session.commit()
                                    print(f"💾 Database updated for {locker_mac}")
                            else:
                                print(f"⚠️ Locker {locker_mac} not found in database")
                    
                    except Exception as db_error:
                        print(f"❌ Database error for {locker_mac}: {db_error}")
                    
        except aiomqtt.MqttError as e:
            print(f"⚠️ MQTT Error: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Critical MQTT Error: {e}")
            await asyncio.sleep(5)
