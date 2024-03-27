# tasmota_power_monitor

This textual / aiomqtt python application listens to MQTT for energy information from Tasmota devices.

### Configuring the Tasmota Device:
On the Tasmota device a rule is needed to generate the data. The rule can be added to the device via the web console and uses var1-4:  

    Rule3  
    on energy#voltage!=%var1% do var1 %value% endon  
    on energy#current!=%var2% do var2 %value% endon  
    on energy#power!=%var3% do var3 %value% endon  
    on energy#factor!=%var4% do var4 %value% endon 

More information is available on rules:https://tasmota.github.io/docs/Rules/.

### Install required libraries  
    pip -i aiomqtt textual

### Configure tpmtable.py
Add the information specific for the environment:  

    MQTT_HOST = 'fill in your mqtt host here'
    MQTT_PORT = 'add your mqtt port here'
    MQTT_USER = "name that user"  
    MQTT_PASS = "password"  
    CLIENT_ID = 'put your client id here'

### Run
    python tpmtable.py

### Screen
    Now split, the left is the powertable (for now) and the right is the log widget  
    to dump mqtt messages that don't match, input or other stuff.

### Input
    sub <topic> or cmnd <topic> <action> <message or None if left off>

## Special thanks to
[vherolf](https://github.com/vherolf) for extending what I started.
I've now included some of that extension into this update.    
The textualize and aiomqtt developers,
Yeah!