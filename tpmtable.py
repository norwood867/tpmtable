"""
This program was put together to use when I'm calibrating the power monitoring
on my Tasmota devices.
"""
import json
from aiomqtt import Client
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Header

try:
    from config import MQTT_HOST, MQTT_PORT, CLIENT_ID
except ModuleNotFoundError as _:
    MQTT_HOST = 'fill in your mqtt host here'
    MQTT_PORT = 'add your mqtt port here'
    CLIENT_ID = 'put your client id here'


"""
This rule is required to get the power monitoring data from the Tasmota devices.
For help with rules checkout https://tasmota.github.io/docs/Rules/.
    Rule3
        on energy#voltage!=%var1% do var1 %value% endon 
        on energy#current!=%var2% do var2 %value% endon 
        on energy#power!=%var3% do var3 %value% endon 
        on energy#factor!=%var4% do var4 %value% endon
"""

def is_json(myjson):
    """check if a string is json"""
    try:
        j = json.loads(myjson)
    except ValueError as _:
        return ""
    return j

class PowerCal(App):
    """main widget with data table"""
    TITLE = "Tasmotas"

    monitor = ["topic", "name", "voltage", "current", "power", "factor"]
    var = {f"Var{k+1}": v for k, v in enumerate(monitor[2:])}

    def compose(self) -> ComposeResult:
        yield Header(name="Tasmotas", show_clock=False)
        yield Horizontal(
            DataTable(id="tuning", show_cursor=False, classes="box"),
        )


    def on_mount(self):
        table = self.query_one("#tuning", DataTable)
        for col in self.monitor:
            table.add_column(col, key=col)
        self.mqtt()


    def sort_by_name(self) -> None:
        table = self.query_one("#tuning", DataTable)
        table.sort("name", key=lambda x: "-" if isinstance(x, type(None)) else x)

    @work(exclusive=True)
    async def mqtt(self):
        """_summary_"""
        tasmota = {}
        table = self.query_one("#tuning", DataTable)
        async with Client(MQTT_HOST, port=MQTT_PORT, identifier=CLIENT_ID) as client:
            await client.subscribe("tuning/#")
            await client.subscribe("tele/+/LWT")
            await client.subscribe("stat/+/RESULT")
            await client.publish("cmnd/tasmotas/rule3", "1")
            async for message in client.messages:
                t = message.topic.value
                _, msgid, action = t.split("/")
                msg = message.payload.decode("utf-8")
                jmsg = is_json(msg)

                if msgid not in tasmota and msgid.startswith("tasmota"):
                    tasmota[msgid] = table.add_row(msgid, key=msgid)
                    await client.publish(f"cmnd/{msgid}/devicename", "")
                    continue

                if action == "RESULT" and jmsg:
                    key, value = list(jmsg.items())[0]
                    if key in "DeviceName":
                        table.update_cell(
                            row_key=tasmota[msgid],
                            column_key="name",
                            value=value,
                            update_width=True,
                        )
                        self.sort_by_name()
                    elif key in self.var:
                        table.update_cell(
                            row_key=tasmota[msgid], column_key=self.var[key], value=value
                        )

if __name__ == "__main__":
    app = PowerCal()
    app.run()
