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
from textual.suggester import SuggestFromList, Suggester
from data import devices, actions
from typing import Optional

try:
    from config import CLIENT_ID, DEFAULT_SUB_LIST, MQTT_HOST, MQTT_PORT, MQTT_PASS, MQTT_USER
except ModuleNotFoundError as _:
    MQTT_HOST = "fill in your mqtt host here"
    MQTT_PORT = "add your mqtt port here"
    MQTT_USER = "name that user"
    MQTT_PASS = "password"
    CLIENT_ID = "put your client id here"


def is_json(myjson):
    """check if a string is json"""
    try:
        j = json.loads(myjson)
    except ValueError as _:
        return ""
    return j



class SuggestionsUpdatable(Suggester):
    """a suggester that can be updated with new topics and devices"""
    def __init__(self) -> None:
        super().__init__(use_cache=False)
        self.actions = [x.lower() for x in actions]
        self.devices = devices
        self.choices = {}

        for device in devices:
            self.choices[device] = self.actions
        self.choices['unsub'] = []

    def action_remove_sub(self, unsub) -> bool:
        """unsubscribe from a topic"""
        try:
            self.choices['unsub'].remove(unsub)
        except ValueError as _:
            return False
        return True

    def action_add_topic(self, name: str) -> None:
        """add a topic to the list of subscribed topics"""
        self.choices['unsub'].append(name)

    def action_add_device(self, name: str) -> None:
        """add a device to the list of devices"""
        self.choices[name] = self.actions

    def create_lookup_list(self, a: list, b: list, prepend: Optional[list] = None):
        '''create the combined lists'''
        if prepend is None:
            prepend = []
        return prepend + [f'{x} {y}' for x in a for y in b]

    def action_input_previous(self, _current) -> None:
        '''move to the previous suggestion'''
        if ' ' in _current:
            pieces = _current.split(' ')
        else:
            pieces = [_current]
        
        if pieces[0] not in self.choices:
            return self.get_suggestion(_current)
        try:
            _newcurrent = self.choices[
                            self.choices[
                                pieces[0]].index(pieces[1]) - 1
                                    % len(self.choices[pieces[0]])]
        except ValueError as _:
            return self.get_suggestion(_current)
        return _newcurrent

    def action_input_next(self, _current) -> None:
        '''move to the next suggestion'''
        if ' ' in _current:
            pieces = _current.split(' ')
        else:
            pieces = [_current]
        if pieces[0] not in self.choices:
            return self.get_suggestion(_current)
        try:
            _newcurrent = self.choices[self.choices[pieces[0]].index(pieces[1]) + 1 ]
                                    #    % len(self.choices[pieces[0]])]
        except ValueError as _:
            return self.get_suggestion(_current)
        return _newcurrent
    
    async def get_suggestion(self, value: str) -> str | None:
        """get the first match on topics and commands"""
        if ' ' in value:
            v = value.split(' ')
        else:
            v = [value]
        
        if v[0] not in self.choices:
            try:
                r = next(i for i in list(self.choices) if i.startswith(value))
                return r
            except StopIteration as _:
                return None
        if len(v) > 1:
            try:
                r = next(i for i in self.choices[v[0]] if i.startswith(v[1]))
                return f'{v[0]} {r}'
            except StopIteration as _:
                return v[0]

    #self.query_one(Input).suggester.action_add_device('ebike') to add ebike


class PowerCal(App):
    """main widget with data table"""

    TITLE = "Tasmotas"

    CSS_PATH = "tpmtable.tcss"


    AUTO_FOCUS = "#input"



    # client=None
    def __init__(self):
        super().__init__()
        self.client = None

    BINDINGS = {
        ("up", "input_previous", "previous"),
        ("down", "input_next", "next"),
    }

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
            placeholder="<topic or devicename> <action> <value> OR . <action> <topic>",
            suggester=SuggestionsUpdatable(),
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
                self.query_one(Input).suggester.action_add_device(value)
                self.sort_by_name()
            elif key in self.var:
                power_table.update_cell(
                    row_key=msgid, column_key=self.var[key], value=value
                )
            else:
                mqttlog.write_line(f"mqtt_results {msgid} {action} {jmsg}")
        else:
            mqttlog.write_line(f"mqtt_results {msgid} {action} {jmsg}")


    def action_input_previous(self) -> None:
        '''move to the previous suggestion'''
        self.query_one(Input).value = self.query_one(
            Input
        ).suggester.action_input_previous(self.query_one(Input)._suggestion)


    def action_input_next(self) -> None:
        '''move to the next suggestion'''
        self.query_one(Input).value = self.value = self.query_one(
            Input
        ).suggester.action_input_previous(self.query_one(Input)._suggestion)


    @on(Input.Submitted)
    async def input_sent(self, message: Input.Submitted) -> None:
        '''listen for input and send to mqtt server'''
        log = self.query_one("#mqttlog", Log)
        log.write_line(f"{message}")
        m = message.value.split(" ")
        if message.value.startswith("."):
            #do the attion
            pass
        else:
            if 'all' in m[0]:
                m[0] = 'tasmotas'
            while len(m) != 3:
                m.append(None)
            await self.client.publish(f"cmnd/{m[0]}/{m[1]}", m[2])


    @work(exclusive=False)
    async def mqtt(self) -> None:
        """interaction with mqtt server"""
        tasmota = {}
        power_table = self.query_one("#tuning", DataTable)
        mqttlog = self.query_one("#mqttlog", Log)

        async with Client(
            MQTT_HOST, port=MQTT_PORT, identifier=CLIENT_ID, username=MQTT_USER, password=MQTT_PASS
        ) as self.client:
            for sub in DEFAULT_SUB_LIST:
                await self.client.subscribe(sub)
                self.query_one(Input).suggester.action_add_topic(sub)

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


                if (
                    msgid is not None
                    and msgid not in tasmota
                    and msgid.startswith("tasmota")
                ):
                    tasmota[msgid] = power_table.add_row(msgid, key=msgid)
                    await self.client.publish(f"cmnd/{msgid}/devicename", "")
                    self.query_one(Input).suggester.action_add_device(msgid)
                    continue

                mqttlog.write_line(f"main section: {msgid} {jmsg}")


if __name__ == "__main__":
    app = PowerCal()
    app.run()



#to delete
        # if message.value.startswith("sub"):
        #     await self.client.subscribe(m[1])
        # elif message.value.startswith("unsub"):
        #     await self.client.unsubscribe(m[1])
        # elif message.value.startswith("cmnd"):
        #     while len(m) != 4:
        #         m.append(None)
        #     await self.client.publish(f"cmnd/{m[1]}/{m[2]}", m[3])
        # else:
        #     self.notify(f"Unknown: {message.value}")
            # log.write_line(f"{message.value}")