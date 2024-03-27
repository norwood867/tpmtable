"""
This program was put together to use when I'm calibrating the power monitoring
on my Tasmota devices.
"""

import json
from collections import defaultdict
from datetime import datetime as dt
from datetime import timedelta

from aiomqtt import Client
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import DataTable, Header, Input, Log

try:
    from config import CLIENT_ID, DEFAULT_SUB_LIST, MQTT_HOST, MQTT_PORT, MQTT_PASS, MQTT_USER
except ModuleNotFoundError as _:
    MQTT_HOST = "fill in your mqtt host here"
    MQTT_PORT = "add your mqtt port here"
    MQTT_USER = "name that user"
    MQTT_PASS = "password"
    CLIENT_ID = "put your client id here"
    DEFAULT_SUB_LIST = ["tuning/#", "tele/+/LWT", "stat/+/RESULT", "tui/#"]


def is_json(myjson):
    """check if a string is json"""
    try:
        j = json.loads(myjson)
    except ValueError as _:
        return ""
    return j


class Temps:
    """running averages"""

    def __init__(self):
        # self.temp_last_minute = []
        self.temp_last_five = defaultdict(dict)

    def avg_temp(self, temp_json):
        """calculate the average temperature over the last 5 minutes
            ugh, this is hard to read, clean it up later"""
        minute1 = []
        self.temp_last_five[temp_json["name"]][dt.fromisoformat(temp_json["t"])] = (
            temp_json["f"]
        )
        keys = list(self.temp_last_five[temp_json["name"]].keys())
        for k in keys:
            if k < dt.now() - timedelta(minutes=5):
                del self.temp_last_five[temp_json["name"]][k]
            elif k > dt.now() - timedelta(minutes=1):
                minute1.append(self.temp_last_five[temp_json["name"]][k])
        return sum(self.temp_last_five[temp_json["name"]].values()) / len(
            self.temp_last_five[temp_json["name"]]
        ), sum(minute1) / len(minute1)


class PowerCal(App):
    """main widget with data table"""

    TITLE = "Tasmotas"
    # Mimicking the CSS syntax
               # Color name
    # widget.styles.color = "$accent"            # Textual variable
    # widget.styles.tint = "hsl(300, 20%, 70%)"  # HSL description

    CSS_PATH = "tpmtable.tcss"

    AUTO_FOCUS = "#input"

    # client=None
    def __init__(self):
        super().__init__()
        self.client = None

    monitor = ["topic", "name", "voltage", "current", "power", "factor"]
    var = {f"Var{k+1}": v for k, v in enumerate(monitor[2:])}

    def compose(self) -> ComposeResult:
        yield Header(name="Tasmotas", id="header", show_clock=False)
        yield Horizontal(
            DataTable(id="tuning", show_cursor=False, show_header=True),
            Log(id="mqttlog"),
        )
        yield Input(
            id="input",
            placeholder="sub <topic> or cmnd <topic or devicename> <action> <value>",
        )

    def on_mount(self) -> None:
        '''set up the table and mqtt connection'''
        self.styles.color = "red"
        power_table = self.query_one("#tuning", DataTable)
        for col in self.monitor:
            power_table.add_column(col, key=col)
        self.mqtt()

    def sort_by_name(self) -> None:
        '''sort the table by device name'''
        power_table = self.query_one("#tuning", DataTable)
        power_table.sort("name", key=lambda x: "-" if isinstance(x, type(None)) else x)

    def mqtt_results(
        self,
        power_table,
        mqttlog,
        msgid,
        action,
        jmsg,
    ) -> None:
        """update the table with the results from the mqtt server"""
        if action == "RESULT" and jmsg:
            key, value = list(jmsg.items())[0]
            if key in "DeviceName":
                power_table.update_cell(
                    row_key=msgid,
                    column_key="name",
                    value=value,
                    update_width=True,
                )
                self.sort_by_name()
            elif key in self.var:
                power_table.update_cell(
                    row_key=msgid, column_key=self.var[key], value=value
                )
            else:
                mqttlog.write_line(f"mqtt_results {msgid} {action} {jmsg}")
        else:
            mqttlog.write_line(f"mqtt_results {msgid} {action} {jmsg}")


    @on(Input.Submitted)
    async def input_sent(self, message: Input.Submitted) -> None:
        '''listen for input and send to mqtt server'''
        log = self.query_one("#mqttlog", Log)
        log.write_line(f"{message}")
        m = message.value.split(" ")

        if message.value.startswith("sub"):
            await self.client.subscribe(m[1])

        elif message.value.startswith("cmnd"):
            while len(m) != 4:
                m.append(None)
            await self.client.publish(f"cmnd/{m[1]}/{m[2]}", m[3])
        else:
            self.notify(f"Unknown: {message.value}")
            # log.write_line(f"{message.value}")

    @work(exclusive=False)
    async def mqtt(self) -> None:
        """interaction with mqtt server"""
        tasmota = {}
        power_table = self.query_one("#tuning", DataTable)
        mqttlog = self.query_one("#mqttlog", Log)

        living_room = Temps()

        async with Client(
            MQTT_HOST, port=MQTT_PORT, identifier=CLIENT_ID, username=MQTT_USER, password=MQTT_PASS
        ) as self.client:
            for sub in DEFAULT_SUB_LIST:
                await self.client.subscribe(sub)

            for i in range(1, 4):
                await self.client.publish(f"cmnd/tasmotas/var{i}", "")

            async for message in self.client.messages:
                t = message.topic.value
                if t.count("/") == 0:
                    msgid = None
                    action = t
                if t.count("/") == 1:
                    msgid, action = t.split("/")
                elif t.count("/") == 2:
                    _, msgid, action = t.split("/")
                msg = message.payload.decode("utf-8")
                jmsg = is_json(msg)

                if message.topic.matches("stat/+/RESULT"):
                    self.mqtt_results(power_table, mqttlog, msgid, action, jmsg)
                    continue

                if message.topic.matches("temp_json"):
                    m5, m1 = living_room.avg_temp(jmsg)
                    if jmsg["name"] == "living":
                        mqttlog.write_line(
                            f'{jmsg['t']} {jmsg['name']}: {m5:.2f} 5m, {m1:.2f} 1m'
                        )
                    continue

                if (
                    msgid is not None
                    and msgid not in tasmota
                    and msgid.startswith("tasmota")
                ):
                    tasmota[msgid] = power_table.add_row(msgid, key=msgid)
                    await self.client.publish(f"cmnd/{msgid}/devicename", "")
                    continue

                mqttlog.write_line(f"main section: {msgid} {jmsg}")


if __name__ == "__main__":
    app = PowerCal()
    app.run()
