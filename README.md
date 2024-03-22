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
    CLIENT_ID = 'put your client id here'

### Run
    python tpmtable.py
