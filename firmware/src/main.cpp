#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiManager.h>
#include <Preferences.h>

// Locker Configuration
const int RELAY_PIN = 2;

// Storage for configuration
Preferences preferences;
String LOCKER_ID = "locker_01";
String MQTT_SERVER = "192.168.1.100";
int MQTT_PORT = 1883;

// MQTT Topics
String commandTopic = "lockngo/" + String(LOCKER_ID) + "/command";
String statusTopic = "lockngo/" + String(LOCKER_ID) + "/status";

// WiFi and MQTT Clients
WiFiClient espClient;
PubSubClient client(espClient);

/**
 * MQTT Callback - The Brain
 * Handles incoming MQTT messages and controls the lock
 */
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  // Convert payload to string
  String message = "";
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  // Check if this is the command topic
  if (String(topic) == commandTopic) {
    // Handle OPEN command
    if (message == "OPEN") {
      Serial.println("Opening Lock...");
      
      // Activate relay (HIGH = lock opens)
      digitalWrite(RELAY_PIN, HIGH);
      
      // Simulate lock opening duration (2 seconds)
      delay(2000);
      
      // Deactivate relay (LOW = lock closed/neutral)
      digitalWrite(RELAY_PIN, LOW);
      
      // Publish status update
      client.publish(statusTopic.c_str(), "OPENED");
      Serial.println("Lock opened and status published");
    }
  }
}

/**
 * Setup WiFi using WiFiManager
 * Creates AP "LockGo-Setup" if no saved credentials
 */
void setupWiFi() {
  WiFiManager wifiManager;
  
  // Custom parameters for MQTT and Locker ID
  WiFiManagerParameter custom_mqtt_server("server", "MQTT Server IP", MQTT_SERVER.c_str(), 40);
  WiFiManagerParameter custom_mqtt_port("port", "MQTT Port", String(MQTT_PORT).c_str(), 6);
  WiFiManagerParameter custom_locker_id("locker_id", "Locker ID", LOCKER_ID.c_str(), 20);
  
  wifiManager.addParameter(&custom_mqtt_server);
  wifiManager.addParameter(&custom_mqtt_port);
  wifiManager.addParameter(&custom_locker_id);
  
  // Set timeout for config portal (3 minutes)
  wifiManager.setConfigPortalTimeout(180);
  
  Serial.println("Starting WiFiManager...");
  Serial.println("If no saved WiFi, connect to 'LockGo-Setup' (password: lockgo2025)");
  
  // Try to connect, if fails - start config portal
  if (!wifiManager.autoConnect("LockGo-Setup", "lockgo2025")) {
    Serial.println("Failed to connect and timeout reached");
    Serial.println("Restarting...");
    delay(3000);
    ESP.restart();
  }
  
  // Connected!
  Serial.println("✅ WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  
  // Save custom parameters
  MQTT_SERVER = custom_mqtt_server.getValue();
  MQTT_PORT = String(custom_mqtt_port.getValue()).toInt();
  LOCKER_ID = custom_locker_id.getValue();
  
  // Save to preferences
  preferences.begin("lockgo", false);
  preferences.putString("mqtt_server", MQTT_SERVER);
  preferences.putInt("mqtt_port", MQTT_PORT);
  preferences.putString("locker_id", LOCKER_ID);
  preferences.end();
  
  Serial.println("Configuration saved:");
  Serial.print("  MQTT Server: ");
  Serial.println(MQTT_SERVER);
  Serial.print("  MQTT Port: ");
  Serial.println(MQTT_PORT);
  Serial.print("  Locker ID: ");
  Serial.println(LOCKER_ID);
}

/**
 * Reconnect to MQTT broker if connection is lost
 */
void reconnectMQTT() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection to ");
    Serial.print(MQTT_SERVER);
    Serial.print(":");
    Serial.println(MQTT_PORT);
    
    // Attempt to connect with locker ID as client ID
    if (client.connect(LOCKER_ID)) {
      Serial.println("MQTT connected!");
      
      // Subscribe to command topic
      client.subscribe(commandTopic.c_str());
      Serial.print("Subscribed to: ");
      Serial.println(commandTopic);
    } else {
      Serial.print("MQTT connection failed, rc=");
      Serial.print(client.state());
      Serial.println(" Retrying in 5 seconds...");
      delay(5000);
    }
  }
}

/**
 * Setup function - Initialize hardware and connections
 */
void setup() {
  // Initialize Serial communication
  Serial.begin(115200);
  delay(1000);
  Serial.println("\nLock&Go Locker Controller Starting...");
  
  // Configure relay pin as output
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Ensure relay starts in LOW state
  Serial.print("Relay pin configured: GPIO ");
  Serial.println(RELAY_PIN);
  
  // Connect to WiFi
  reconnectWiFi();
  
  // Configure MQTT client
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(mqttCallback);
  
  // Connect to MQTT broker
  reconnectMQTT();
  
  Serial.println("Setup complete! Waiting for commands...");
}

/**
 * Main loop - Maintain connections and process MQTT messages
 */
void loop() {
  // Ensure WiFi is connected (reconnect if lost)
  reconnectWiFi();
  
  // Ensure MQTT is connected (reconnect if lost)
  if (!client.connected()) {
    reconnectMQTT();
  }
  
  // Process MQTT messages
  client.loop();
}

