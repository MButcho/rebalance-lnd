#!/usr/bin/env python3

import argparse
import os
import subprocess
import platform
import random
import sys
import json
from datetime import datetime, timedelta

from yachalk import chalk

from lnd import Lnd
from logic import Logic
from output import Output, format_alias, format_alias_red, format_alias_green, format_ppm, format_amount, format_amount_green, format_amount_white, format_amount_white_s, \
    format_boring_string, print_bar, format_channel_id, format_error, format_boring_string, format_amount_red, format_amount_red_s


# define nodes, fee adjustment, ...
daily_update = 22 # hour must be 22 on hourly update
routers = []
vampires = []
vampire_fees = []
vampire_adjust = 0.025
sources = []
channels = []
script_path = os.path.dirname(sys.argv[0])
node_file_path = script_path+'/nodes.conf'

if os.path.isfile(node_file_path) and os.stat(node_file_path).st_size > 0:
    nodes_file = open(node_file_path, 'r')
    nodes_arr = nodes_file.read().split('\n')
    nodes_file.close()
    for _node in nodes_arr:
        _node_arr = _node.split(';')
        if _node_arr[0][0:1] != "#":
            if len(_node_arr) == 2 or len(_node_arr) == 4:
                if _node_arr[1] == "router":
                    routers.append(_node_arr[0])
                if _node_arr[1] == "vampire":
                    vampires.append(_node_arr[0])
                    if len(_node_arr) == 4:
                        vampire_fees.append(_node_arr[0] + ";" + _node_arr[2] + ";" + _node_arr[3])
                    else:
                        sys.exit("Please edit nodes.conf and add 4 arguments for vampire " + _node_arr[0])
                if _node_arr[1] == "source":
                    sources.append(_node_arr[0])
else:
    sys.exit("Please create nodes.conf (copy and edit nodes.conf.sample)")

bos_file_path = script_path+'/bos.conf'
#fee_lowest = 49
bos_arr = []
fee_arr = []
vamp_arr = []
#events_target_high = 50
#events_target_medium = 25
events_1d_high = 200
events_1d_low = 100
fee_adjustment = False # True = fee adjustments for single node based on events and overall
fee_adjust_file_path = script_path+'/fee_adjust.conf'
if os.path.isfile(fee_adjust_file_path) and os.stat(fee_adjust_file_path).st_size > 0: # if empty file
    fee_adjust_file = open(fee_adjust_file_path, 'r')
    fee_adjust = float(fee_adjust_file.read())        
else:
    fee_adjust_file = open(fee_adjust_file_path, 'w')
    fee_adjust = 1
    fee_adjust_file.write(str(fee_adjust))
fee_adjust_file.close()

class Rebalance:
    def __init__(self, arguments):
        self.lnd = Lnd(arguments.lnddir, arguments.grpc, arguments.network)
        self.output = Output(self.lnd)
        self.min_amount = arguments.min_amount
        self.arguments = arguments
        self.first_hop_channel_id = self.parse_channel_id(vars(arguments)["from"])
        self.last_hop_channel_id = self.parse_channel_id(arguments.to)
        self.first_hop_channel = None
        self.last_hop_channel = None
        self.min_local = arguments.min_local
        self.min_remote = arguments.min_remote

    @staticmethod
    def parse_channel_id(id_string):
        if not id_string:
            return None
        arr = None
        if ":" in id_string:
            arr = id_string.rstrip().split(":")
        elif "x" in id_string:
            arr = id_string.rstrip().split("x")
        if arr:
            return (int(arr[0]) << 40) + (int(arr[1]) << 16) + int(arr[2])
        return int(id_string)

    def get_sort_key(self, channel):
        rebalance_amount = self.get_rebalance_amount(channel)
        if rebalance_amount >= 0:
            return (
                self.lnd.get_ppm_to(channel.chan_id) * rebalance_amount,
                get_remote_available(channel) - get_local_available(channel)
            )
        return rebalance_amount, self.lnd.get_ppm_to(channel.chan_id)
        
    def get_sort_key_ratio(self, channel):
        return get_local_ratio(channel)

    def get_scaled_min_local(self, channel):
        local_available = get_local_available(channel)
        remote_available = get_remote_available(channel)
        if local_available + remote_available >= self.min_local + self.min_remote:
            return self.min_local
        return self.min_local / (self.min_local + self.min_remote) * (local_available + remote_available)

    def get_scaled_min_remote(self, channel):
        local_available = get_local_available(channel)
        remote_available = get_remote_available(channel)
        if local_available + remote_available >= self.min_local + self.min_remote:
            return self.min_remote
        return self.min_remote / (self.min_local + self.min_remote) * (local_available + remote_available)

    def get_rebalance_amount(self, channel):
        local_available = get_local_available(channel)
        remote_available = get_remote_available(channel)
        too_small = local_available + remote_available < self.min_local + self.min_remote
        if too_small:
            return int(self.get_scaled_min_local(channel) - local_available)
        if local_available < self.min_local:
            return self.min_local - local_available
        if remote_available < self.min_remote:
            return remote_available - self.min_remote
        return 0

    def get_amount(self):
        amount = None
        if self.arguments.amount:
            amount = self.arguments.amount
            if not self.arguments.adjust_amount_to_limits:
                return amount

        should_send = 0
        can_send = 0
        if self.first_hop_channel:
            should_send = -self.get_rebalance_amount(self.first_hop_channel)
            can_send = self.get_amount_can_send(self.first_hop_channel)

            if can_send < 0:
                from_alias = self.lnd.get_node_alias(self.first_hop_channel.remote_pubkey)
                print(
                    f"Error: source channel {format_channel_id(self.first_hop_channel.chan_id)} to "
                    f"{format_alias(from_alias)} needs to {chalk.green('receive')} funds to be within bounds,"
                    f" you want it to {chalk.red('send')} funds. "
                    "Specify amount manually if this was intended."
                )
                return 0

        should_receive = 0
        can_receive = 0
        if self.last_hop_channel:
            should_receive = self.get_rebalance_amount(self.last_hop_channel)
            can_receive = self.get_amount_can_receive(self.last_hop_channel)

            if can_receive < 0:
                to_alias = self.lnd.get_node_alias(self.last_hop_channel.remote_pubkey)
                print(
                    f"Error: target channel {format_channel_id(self.last_hop_channel.chan_id)} to "
                    f"{format_alias(to_alias)} needs to {chalk.green('send')} funds to be within bounds, "
                    f"you want it to {chalk.red('receive')} funds."
                    f" Specify amount manually if this was intended."
                )
                return 0

        if self.first_hop_channel and self.last_hop_channel:
            computed_amount = max(min(can_receive, should_send), min(can_send, should_receive))
        elif self.first_hop_channel:
            computed_amount = should_send
        else:
            computed_amount = should_receive

        computed_amount = int(computed_amount)
        if amount is not None:
            if computed_amount >= 0:
                computed_amount = min(amount, computed_amount)
            else:
                computed_amount = max(-amount, computed_amount)
        return computed_amount

    def get_amount_can_send(self, channel):
        return get_local_available(channel) - self.get_scaled_min_local(channel)

    def get_amount_can_receive(self, channel):
        return get_remote_available(channel) - self.get_scaled_min_remote(channel)

    def get_channel_for_channel_id(self, channel_id):
        if not channel_id:
            return None
        for channel in self.lnd.get_channels():
            if channel.chan_id == channel_id:
                return channel
        raise Exception(f"Unable to find channel with ID {channel_id}")

    def get_private_channels(self):
        return self.lnd.get_channels(active_only=True,private_only=True),

    def list_channels(self, reverse=False):
        sorted_channels = sorted(
            self.lnd.get_channels(active_only=True),
            key=lambda c: self.get_sort_key(c),
            reverse=reverse
        )
        for channel in sorted_channels:
            self.show_channel(channel, reverse)

    def show_channel(self, channel, reverse=False):
        rebalance_amount = self.get_rebalance_amount(channel)
        if not self.arguments.show_all and not self.arguments.show_only:
            if rebalance_amount < 0 and not reverse:
                return
            if rebalance_amount > 0 and reverse:
                return
            if abs(rebalance_amount) < self.min_amount:
                return
        rebalance_amount_formatted = f"{rebalance_amount:10,}"
        own_ppm = self.lnd.get_ppm_to(channel.chan_id)
        remote_ppm = self.lnd.get_ppm_from(channel.chan_id)
        print(f"Channel ID:       {format_channel_id(channel.chan_id)}")
        print(f"Alias:            {format_alias(self.lnd.get_node_alias(channel.remote_pubkey))}")
        print(f"Pubkey:           {format_boring_string(channel.remote_pubkey)}")
        print(f"Channel Point:    {format_boring_string(channel.channel_point)}")
        print(f"Local ratio:      {get_local_ratio(channel):.3f}")
        print(f"Fee rates:        {format_ppm(own_ppm)} (own), {format_ppm(remote_ppm)} (peer)")
        print(f"Capacity:         {channel.capacity:10,}")
        print(f"Remote available: {format_amount(get_remote_available(channel), 10)}")
        print(f"Local available:  {format_amount_green(get_local_available(channel), 10)}")
        print(f"Rebalance amount: {rebalance_amount_formatted}")
        print(get_capacity_and_ratio_bar(channel, self.lnd.get_max_channel_capacity()))
        print("")

    def list_channels_compact(self):
        candidates = sorted(
            self.lnd.get_channels(active_only=False),
            key=lambda c: self.get_sort_key_ratio(c),
            reverse=True
            )
        
        command = script_path+"/custom.py rebalances -c -d 1 -n 'list'"
        rebalances = json.loads(subprocess.check_output(command, shell = True))
        
        command = "lncli estimatefee '{\"bc1pa44faqxvemdl2yp2cwtkgz9al5ppqvm78820cxgckw5zdnshakes98tuv5\": 1000}' --conf_target 1"
        result = json.loads(subprocess.check_output(command, shell = True))
        btc_fee = int(result['sat_per_vbyte'])
        #btc_fee = 49
        
        inactive = 0
        channels_t = ""
        for candidate in candidates:
            alias = self.lnd.get_node_alias(candidate.remote_pubkey)
            active = bool(candidate.active)
            if not active:
                inactive += 1
            ratio_formatted = get_local_ratio(candidate)
            own_ppm = self.lnd.get_ppm_to(candidate.chan_id)
            remote_ppm = self.lnd.get_ppm_from(candidate.chan_id)
            
            is_router = False
            is_source = False
            is_vampire = False
            
            if alias in routers:
                is_router = True
            if alias in sources:
                is_source = True
                
            if is_source and self.arguments.update:
                if ratio_formatted > 20:
                    command = "bos tags sources --add " + candidate.remote_pubkey
                else:
                    command = "bos tags sources --remove " + candidate.remote_pubkey
                result = subprocess.check_output(command, shell = True)
            
            time = datetime.now()
            _to = int(round(time.timestamp()))
            _from = int(round((time - timedelta(days=1)).timestamp()))
            _from_7d = int(round((time - timedelta(days=7)).timestamp()))
            _from_8h = int(round((time - timedelta(hours=8)).timestamp()))
            events_response = self.lnd.get_events(_from, _to)
            events_response_7d = self.lnd.get_events(_from_7d, _to)
            events_count = 0
            events_count_8h = 0
            volume = 0
            fw_fees = 0
            for event in events_response.forwarding_events:
                if event.chan_id_in == candidate.chan_id or event.chan_id_out == candidate.chan_id:
                    events_count += 1
                    volume += event.amt_in
                    fw_fees += int(event.fee_msat)
                    if event.timestamp > _from_8h:
                        #print(datetime.fromtimestamp(event.timestamp))
                        events_count_8h += 1
            events_count_formatted = format_amount_white_s(events_count, 4)
            #volume_formatted = volume/(10**8)
            
            event_count_sum = events_count
            for _channel in channels:
                if _channel["alias"] == alias:
                    event_count_sum += _channel["events_count"]
            
            volume_7d = 0
            fw_fees_7d = 0
            for event in events_response_7d.forwarding_events:
                if event.chan_id_in == candidate.chan_id or event.chan_id_out == candidate.chan_id:
                    volume_7d += event.amt_in
                    fw_fees_7d += int(event.fee_msat)
            
            indicator = ""
            
            fee_adjusted = own_ppm            
            if is_router or is_source:
                fee_adjusted = round(get_fee_adjusted(ratio_formatted, btc_fee))
            
            # create vampire arr
            if alias in vampires:
                is_vampire = True
                        
                for _vampire_fee_item in vampire_fees:
                    _vampire_fee_arr = _vampire_fee_item.split(';')
                    if _vampire_fee_arr[0] == alias:
                       min_ppm = int(_vampire_fee_arr[1])
                       max_ppm = int(_vampire_fee_arr[2])
                       #print(alias + ", min: " + str(min_ppm) + ", max: " + str(max_ppm))
                
                if own_ppm > remote_ppm:
                    vamp_exists = False
                    for _channel in channels:
                        if _channel["alias"] == alias:
                            vamp_exists = True                            
                    
                    rebalance_count = 0
                    for _rebalance in rebalances:
                        if alias in _rebalance:
                            rebalance_count+=1
                    
                    if event_count_sum == 0 and rebalance_count == 0 and ratio_formatted < 10:
                        if (own_ppm*(1+vampire_adjust)) < max_ppm:
                            fee_adjusted = round(own_ppm*(1+vampire_adjust))
                        else:
                            fee_adjusted = max_ppm
                    elif event_count_sum == 0 and rebalance_count == 0 and ratio_formatted > 50:
                        if (own_ppm*(1-vampire_adjust)) > min_ppm:
                            fee_adjusted = round(own_ppm*(1-vampire_adjust))
                        else:
                            fee_adjusted = min_ppm
                    elif event_count_sum == 0 and rebalance_count == 0 and ratio_formatted > 20:
                        if (own_ppm*(1-(vampire_adjust/2))) > min_ppm:
                            fee_adjusted = round(own_ppm*(1-(vampire_adjust/2)))
                        else:
                            fee_adjusted = min_ppm
                    else:
                        fee_adjusted = own_ppm
                    
                    if vamp_exists:
                        v = 0
                        for _channel in channels:
                            if _channel["alias"] == alias:
                                _fee_adjusted = _channel["fee_adjusted"]
                                #if _channel["events_count"] < events_count:
                                if fee_adjusted < _fee_adjusted:
                                    channels[v] = {"alias":_channel["alias"], "active":_channel["active"], "chan_id":_channel["chan_id"], "channel_point":_channel["channel_point"], "local":_channel["local"], "remote":_channel["remote"], "own_ppm":_channel["own_ppm"], "remote_ppm":_channel["remote_ppm"], "ratio":_channel["ratio"], "events_count":_channel["events_count"], "fee_adjusted":fee_adjusted, "volume":_channel["volume"], "volume_7d":_channel["volume_7d"], "fw_fees":_channel["fw_fees"], "fw_fees_7d":_channel["fw_fees_7d"]}
                                elif fee_adjusted > _fee_adjusted:
                                    fee_adjusted = _fee_adjusted
                            v+=1
            
            channels.append({"alias":alias, "active":active, "chan_id":candidate.chan_id, "channel_point":candidate.channel_point, "local":get_local_available(candidate), "remote":get_remote_available(candidate), "own_ppm":own_ppm, "remote_ppm":remote_ppm, "ratio":ratio_formatted, "events_count":events_count, "fee_adjusted":fee_adjusted, "volume":volume, "volume_7d":volume_7d, "fw_fees":round(fw_fees/1000), "fw_fees_7d":round(fw_fees_7d/1000)})
                
        #events_1d = events_response.last_offset_index
        #fee_adjust_indicator = " -"
        #if self.arguments.update and time.hour == daily_update and fee_adjustment:
        #    if events_1d < events_1d_low and fee_adjust > 0.1:
        #        fee_adjust_file = open(fee_adjust_file_path, 'w')
        #        fee_adjust_file.write(str(round(fee_adjust-0.1, 1)))
        #        fee_adjust_file.close()                
        #    elif events_1d > events_1d_high and fee_adjust < 1.5:
        #        fee_adjust_file = open(fee_adjust_file_path, 'w')
        #        fee_adjust_file.write(str(round(fee_adjust+0.1, 1)))
        #        fee_adjust_file.close()                
        
        if len(candidates) > 0:
            #if events_1d < events_1d_low and fee_adjust > 0.1:
            #    fee_adjust_indicator = format_alias_red(" ⬇️")
            #elif events_1d > events_1d_high and fee_adjust < 1.5:
            #    fee_adjust_indicator = format_alias_green(" ⬆️")
            if self.arguments.forwards == False:
                if fee_adjustment == False:
                    fee_adjust_indicator = " (D)"
                
                if self.arguments.telegram == False and self.arguments.update == False:
                    print(format_boring_string("Channel ID         |     Inbound |    Outbound |  Own |  Rem | Rat. | Adjust |  24h | Alias"))
                
                for _channel in channels:                    
                    alias = _channel["alias"]
                    id_formatted = format_channel_id(_channel["chan_id"])
                    channel_point = _channel["channel_point"]
                    local_formatted = format_amount_green(_channel["local"], 11)
                    remote_formatted = format_amount(_channel["remote"], 11)
                    if _channel["active"]:
                        alias_formatted = format_alias(_channel["alias"][:30])
                    else:
                        alias_formatted = format_alias_red(_channel["alias"][:30])
                    own_ppm = int(_channel["own_ppm"])
                    own_ppm_formatted = format_amount_white_s(_channel["own_ppm"], 4)   
                    remote_ppm = int(_channel["remote_ppm"])
                    remote_ppm_formatted = format_amount_white_s(_channel["remote_ppm"], 4)
                    ratio_formatted = _channel["ratio"]
                    events_count_formatted = format_amount_white_s(_channel["events_count"], 4)
                    fee_adjusted = int(_channel["fee_adjusted"])
                    
                    is_router = False
                    is_source = False
                    is_vampire = False
                    
                    if alias in routers:
                        is_router = True                        
                    if alias in sources:
                        is_source = True
                    if alias in vampires:
                        is_vampire = True
                    
                    # fee adjustment label
                    fee_indicator = ""
                    if (is_router or is_source) and own_ppm != fee_adjusted:
                        if own_ppm > fee_adjusted:
                            fee_indicator = format_alias_green("▼")
                        else:
                            fee_indicator = format_alias_red("▲")
                        adjust = fee_indicator + f'{fee_adjusted:>5}' + indicator
                    elif is_router:
                        adjust = "------"
                    elif is_vampire:
                        if own_ppm != fee_adjusted:
                            if own_ppm > fee_adjusted:
                                fee_indicator = format_alias_green("▼")
                            else:
                                fee_indicator = format_alias_red("▲")
                            adjust = fee_indicator + f'{fee_adjusted:>5}' + indicator
                        else:
                            adjust = "Vampir"
                    elif is_source:
                        adjust = "Source"
                    else:
                        adjust = "Manual"                        
                    
                    if self.arguments.update:
                        if own_ppm != fee_adjusted and (is_vampire == False or self.arguments.vampire):
                            update_policy = self.lnd.update_channel_policy(fee_adjusted, channel_point)
                            print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} [INFO] Updated fee for {alias}, {own_ppm} -> {fee_adjusted}')
                    else:
                        if self.arguments.telegram:
                            #channels_t += alias + ": " + str("{:,}".format(_channel["local"])) + "/" + str("{:,}".format(_channel["remote"])) + "; " + str(own_ppm) + fee_indicator + "/" + str(remote_ppm) + "; " + str(round(ratio_formatted)) + "%; " + str(_channel["events_count"]) + (" 🔴" if _channel["active"] == False else "") + "\n"
                            channels_t += str(round(ratio_formatted)) + "% (" + str(own_ppm) + fee_indicator + "/" + str(remote_ppm) + ") • " + str(_channel["events_count"]) + " • " + alias + (" 🔴" if _channel["active"] == False else "") + "\n"
                        else:
                            print(f"{id_formatted} | {local_formatted} | {remote_formatted} | {own_ppm_formatted} | {remote_ppm_formatted} | {str(round(ratio_formatted)).rjust(3)}% | {adjust} | {events_count_formatted} | {alias_formatted}")
            
            if self.arguments.update == False:
                forwards_sorted = sorted(channels, key = lambda item:item['events_count'], reverse = True)
                if self.arguments.telegram:
                    if inactive == 0:
                        icon = "🟢 "
                    else:
                        icon = "🔴 "
                    u = 0
                    all_volume = 0
                    all_volume_7d = 0
                    all_fw_fees = 0
                    all_fw_fees_7d = 0
                    for _forward in forwards_sorted:
                        all_volume += _forward['volume']
                        all_volume_7d += _forward['volume_7d']
                        all_fw_fees += _forward['fw_fees']
                        all_fw_fees_7d += _forward['fw_fees_7d']
                        if _forward['events_count'] > 0:
                            u+=1
                    if self.arguments.forwards:
                        forwards_txt = "Used: <b>" + str(u) + "</b> • "
                    else:
                        forwards_txt = ""
                    print(icon + forwards_txt + "Status: " + str(len(candidates)) + "/" + (str(inactive) if inactive == 0 else str(inactive)) + " • 24h: <b>" + str(events_response.last_offset_index) + "</b> (<i>" + format_amount_green(round(all_volume/2),0) + " • " + format_amount_green(round(all_fw_fees/2),0) + "</i>) • 7d: <b>" + str(events_response_7d.last_offset_index) + "</b> (<i>" + format_amount_green(round(all_volume_7d/2),0) + " • " + format_amount_green(round(all_fw_fees_7d/2),0) + "</i>)")
                    if self.arguments.forwards == False:
                        if len(channels_t) > 0:
                            print(channels_t)
                        else:
                            print("All channels are active")
                    else:
                        for _forward in forwards_sorted:
                            _events_count = _forward['events_count']
                            _volume = format_amount_green(_forward['volume'],0)
                            if _events_count > 0:
                                print("<b>" + str(_events_count) + "</b> via " + _forward['alias'] + " for <i>" + str(_volume) + "</i>")
                else:
                    all_volume = 0
                    all_volume_7d = 0
                    all_fw_fees = 0
                    all_fw_fees_7d = 0
                    for _forward in forwards_sorted:
                        _events_count = _forward['events_count']
                        _volume = format_amount_green(_forward['volume'], 11)
                        all_volume += _forward['volume']
                        all_volume_7d += _forward['volume_7d']
                        all_fw_fees += _forward['fw_fees']
                        all_fw_fees_7d += _forward['fw_fees_7d']
                        if _events_count > 0:
                            if self.arguments.forwards:
                                print(str(format_amount_red_s(_events_count,4)) + " | " + str(_volume) + " | " + _forward['alias'])
                    print(format_boring_string("Nodes: ") + str(format_amount_green(len(candidates),1)) + "/" + (str(format_boring_string(inactive)) if inactive == 0 else str(format_amount_red(inactive, 1))) + " | " + format_boring_string("24 hours: ") + str(events_response.last_offset_index) + " • " + format_amount_green(round(all_volume/2), 0) + " • " + format_amount_red(round(all_fw_fees/2), 0) + " | " + format_boring_string("7 days: ") + str(events_response_7d.last_offset_index) + " • " + format_amount_green(round(all_volume_7d/2), 0) + " • " + format_amount_red(round(all_fw_fees_7d/2), 0))

            # solve vampires and bos
            bos_file = open(bos_file_path, 'w')
            for _channel in channels:
                if int(_channel["own_ppm"]) < 5000:
                    is_vampire = False
                    if _channel["alias"] in vampires:
                        is_vampire = True
                    
                    if is_vampire and _channel["ratio"] < 50 and _channel["own_ppm"] > _channel["remote_ppm"]:
                        vamp_exists = False
                        for _vamp_arr in vamp_arr:
                            if _vamp_arr["alias"] == _channel["alias"]:
                                vamp_exists = True
                                    
                        if not vamp_exists:
                            if _channel["active"]:
                                if self.arguments.vampire:
                                    _fee_adjusted = _channel["fee_adjusted"]
                                else:
                                    _fee_adjusted = _channel["own_ppm"]                                
                                vamp_arr.append({'alias':_channel["alias"], 'fee_adjusted':_fee_adjusted, 'ratio':_channel["ratio"], 'events_count':_channel["events_count"]})
                        else:
                            v = 0
                            for _vamp_arr in vamp_arr:
                                if _vamp_arr["alias"] == _channel["alias"]:
                                    if _vamp_arr["events_count"] < _channel["events_count"]:
                                        vamp_arr[v] = {'alias':_channel["alias"], 'fee_adjusted':_channel["fee_adjusted"], 'ratio':_channel["ratio"], 'events_count':_channel["events_count"]}
                                v+=1
                        
            
            for _vamp_arr_item in vamp_arr:
                bos_arr.append(_vamp_arr_item["alias"] + ";" + str(_vamp_arr_item["fee_adjusted"]) + ";" + str(_vamp_arr_item["ratio"]) + ";" + str(_vamp_arr_item["events_count"]) + "\n")              
            bos_file.writelines(bos_arr[::-1])
            bos_file.close()
        

    def start(self):
        if self.arguments.list_candidates and self.arguments.show_only:
            channel_id = self.parse_channel_id(self.arguments.show_only)
            channel = self.get_channel_for_channel_id(channel_id)
            self.show_channel(channel)
            sys.exit(0)

        if self.arguments.listcompact:
            self.list_channels_compact()
            sys.exit(0)

        if self.arguments.list_candidates:
            incoming = self.arguments.incoming is None or self.arguments.incoming
            if incoming:
                self.list_channels(reverse=False)
            else:
                self.list_channels(reverse=True)
            sys.exit(0)

        if self.first_hop_channel_id == -1:
            self.first_hop_channel = random.choice(self.get_first_hop_candidates())
        else:
            self.first_hop_channel = self.get_channel_for_channel_id(self.first_hop_channel_id)

        if self.last_hop_channel_id == -1:
            self.last_hop_channel = random.choice(self.get_last_hop_candidates())
        else:
            self.last_hop_channel = self.get_channel_for_channel_id(self.last_hop_channel_id)

        amount = self.get_amount()
        if self.arguments.percentage:
            new_amount = int(round(amount * self.arguments.percentage / 100))
            print(f"Using {self.arguments.percentage}% of amount {format_amount(amount)}: {format_amount(new_amount)}")
            amount = new_amount

        if amount == 0:
            print(f"Amount is {format_amount(0)} sat, nothing to do")
            sys.exit(1)

        if amount < self.min_amount:
            print(f"Amount {format_amount(amount)} sat is below limit of {format_amount(self.min_amount)} sat, "
                  f"nothing to do (see --min-amount)")
            sys.exit(1)

        if self.arguments.reckless:
            self.output.print_line(format_error("Reckless mode enabled!"))
        
        if self.arguments.ignore_missed_fee:
            self.output.print_line(format_error("Ignoring missed fee!"))

        fee_factor = self.arguments.fee_factor
        fee_limit_sat = self.arguments.fee_limit
        fee_ppm_limit = self.arguments.fee_ppm_limit
        excluded = []
        if self.arguments.exclude:
            for chan_id in self.arguments.exclude:
                excluded.append(self.parse_channel_id(chan_id))
        if self.arguments.exclude_private:
            private_channels = self.get_private_channels(self)
            for channel in private_channels:
                excluded.append(self.parse_channel_id(channel.chan_id))
        return Logic(
            self.lnd,
            self.first_hop_channel,
            self.last_hop_channel,
            amount,
            excluded,
            fee_factor,
            fee_limit_sat,
            fee_ppm_limit,
            self.min_local,
            self.min_remote,
            self.output,
            self.arguments.reckless,
            self.arguments.ignore_missed_fee
        ).rebalance()

    def get_first_hop_candidates(self):
        result = []
        for channel in self.lnd.get_channels(active_only=True, public_only=self.arguments.exclude_private):
            if self.get_rebalance_amount(channel) < 0:
                result.append(channel)
        return result

    def get_last_hop_candidates(self):
        result = []
        for channel in self.lnd.get_channels(active_only=True):
            if self.get_rebalance_amount(channel) > 0:
                result.append(channel)
        return result


def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    if arguments.incoming is not None and not arguments.list_candidates:
        print(
            "--outgoing and --incoming only work in conjunction with --list-candidates"
        )
        sys.exit(1)

    if arguments.percentage:
        if arguments.percentage < 1 or arguments.percentage > 100:
            print("--percentage must be between 1 and 100")
            argument_parser.print_help()
            sys.exit(1)

    if arguments.reckless and not arguments.amount:
        print("You need to specify an amount for --reckless")
        argument_parser.print_help()
        sys.exit(1)

    if arguments.reckless and arguments.adjust_amount_to_limits:
        print("You must not use -A/--adjust-amount-to-limits in combination with --reckless")
        argument_parser.print_help()
        sys.exit(1)

    if arguments.reckless and not arguments.fee_limit and not arguments.fee_ppm_limit:
        print("You need to specify a fee limit (-fee-limit or --fee-ppm-limit) for --reckless")
        argument_parser.print_help()
        sys.exit(1)

    first_hop_channel_id = vars(arguments)["from"]
    last_hop_channel_id = arguments.to

    no_channel_id_given = not last_hop_channel_id and not first_hop_channel_id
    if not arguments.listcompact and not arguments.list_candidates and no_channel_id_given:
        argument_parser.print_help()
        sys.exit(1)

    return Rebalance(arguments).start()


def get_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lnddir",
        default="_DEFAULT_",
        dest="lnddir",
        help="(default ~/.lnd) lnd directory",
    )
    parser.add_argument(
        "--network",
        default='mainnet',
        dest='network',
        help='(default mainnet) lnd network (mainnet, testnet, simnet, ...)'
    )
    parser.add_argument(
        "--grpc",
        default="localhost:10009",
        dest="grpc",
        help="(default localhost:10009) lnd gRPC endpoint",
    )
    parser.add_argument(
        "-u",
        "--update",
        action='store_true', 
        help="Update fees in conjunction with --compact",
    )
    parser.add_argument(
        "-v",
        "--vampire",
        action='store_true', 
        help="Update fees in conjunction with --compact and --update on vampire nodes",
    )
    parser.add_argument(
        "-g",
        "--telegram",
        action='store_true', 
        help="Output in Telegram format in conjunction with --compact",
    )
    parser.add_argument(
        "-w",
        "--forwards",
        action='store_true', 
        help="Show forwards in conjunction with --compact",
    )
    list_group = parser.add_argument_group(
        "list candidates", "Show the unbalanced channels."
    )
    list_group.add_argument(
        "-l",
        "--list-candidates",
        action="store_true",
        help="list candidate channels for rebalance",
    )

    show_options = list_group.add_mutually_exclusive_group()
    show_options.add_argument(
        "--show-all",
        default=False,
        action="store_true",
        help="also show channels with zero rebalance amount",
    )
    show_options.add_argument(
        "--show-only",
        type=str,
        metavar="CHANNEL",
        help="only show information about the given channel",
    )
    show_options.add_argument(
        "-c",
        "--compact",
        action="store_true",
        dest="listcompact",
        help="Shows a compact list of all channels, one per line including ID, inbound/outbound liquidity, and alias",
    )
    
    direction_group = list_group.add_mutually_exclusive_group()
    direction_group.add_argument(
        "-o",
        "--outgoing",
        action="store_const",
        const=False,
        dest="incoming",
        help="lists channels with less than 1,000,000 (--min-remote) satoshis inbound liquidity",
    )
    direction_group.add_argument(
        "-i",
        "--incoming",
        action="store_const",
        const=True,
        dest="incoming",
        help="(default) lists channels with less than 1,000,000 (--min-local) satoshis outbound liquidity",
    )

    rebalance_group = parser.add_argument_group(
        "rebalance",
        "Rebalance a channel. You need to specify at least"
        " the 'from' channel (-f) or the 'to' channel (-t).",
    )
    rebalance_group.add_argument(
        "-f",
        "--from",
        metavar="CHANNEL",
        type=str,
        help="Channel ID of the outgoing channel (funds will be taken from this channel). "
             "You may also specify the ID using the colon notation (12345:12:1), or the x notation (12345x12x1). "
             "You may also use -1 to choose a random candidate.",
    )
    rebalance_group.add_argument(
        "-t",
        "--to",
        metavar="CHANNEL",
        type=str,
        help="Channel ID of the incoming channel (funds will be sent to this channel). "
             "You may also specify the ID using the colon notation (12345:12:1), or the x notation (12345x12x1). "
             "You may also use -1 to choose a random candidate.",
    )
    amount_group = rebalance_group.add_mutually_exclusive_group()
    rebalance_group.add_argument(
        "-A",
        "--adjust-amount-to-limits",
        action="store_true",
        help="If set, adjust the amount to the limits (--min-local and --min-remote). The script will exit if the "
             "adjusted amount is below the --min-amount threshold. As such, this switch can be used if you do NOT want "
             "to rebalance if the channel is within the limits.",
    )
    amount_group.add_argument(
        "-a",
        "--amount",
        type=int,
        help="Amount of the rebalance, in satoshis. If not specified, "
             "the amount computed for a perfect rebalance will be used",
    )
    amount_group.add_argument(
        "-p",
        "--percentage",
        type=int,
        help="Set the amount to a percentage of the computed amount. "
             "As an example, if this is set to 50, half of the computed amount will be used. "
             "See --amount.",
    )
    rebalance_group.add_argument(
        "--min-amount",
        default=10_000,
        type=int,
        help="(Default: 10,000) If the given or computed rebalance amount is below this limit, nothing is done.",
    )
    rebalance_group.add_argument(
        "--min-local",
        type=int,
        default=1_000_000,
        help="(Default: 1,000,000) Ensure that the channels have at least this amount as outbound liquidity."
    )
    rebalance_group.add_argument(
        "--min-remote",
        type=int,
        default=1_000_000,
        help="(Default: 1,000,000) Ensure that the channels have at least this amount as inbound liquidity."
    )
    rebalance_group.add_argument(
        "-e",
        "--exclude",
        type=str,
        action="append",
        help="Exclude the given channel. Can be used multiple times.",
    )
    rebalance_group.add_argument(
        "--exclude-private",
        action="store_true",
        default=False,
        help="Exclude private channels. This won't affect channel ID used at --to and/or --from but will take effect if you used -1 to get a random channel.",
    )
    rebalance_group.add_argument(
        "--reckless",
        action="store_true",
        default=False,
        help="Allow rebalance transactions that are not economically viable. "
             "You might also want to set --min-local 0 and --min-remote 0. "
             "If set, you also need to set --amount and either --fee-limit or --fee-ppm-limit, and you must not enable "
             "--adjust-amount-to-limits (-A)."
    )
    rebalance_group.add_argument(
        "--fee-factor",
        default=1.0,
        type=float,
        help="(default: 1.0) Compare the costs against the expected "
        "income, scaled by this factor. As an example, with --fee-factor 1.5, "
        "routes that cost at most 150%% of the expected earnings are tried. Use values "
        "smaller than 1.0 to restrict routes to only consider those earning "
        "more/costing less. This factor is ignored with --reckless.",
    )
    rebalance_group.add_argument(
        "--ignore-missed-fee",
        action="store_true",
        default=False,
        help="(default: False) Ignore missed fee from source channel.",
    )
    fee_group = rebalance_group.add_mutually_exclusive_group()
    fee_group.add_argument(
        "--fee-limit",
        type=int,
        help="If set, only consider rebalance transactions that cost up to the given number of satoshis. Note that "
             "the first hop costs are considered, even though you don't have to pay them."
    )
    fee_group.add_argument(
        "--fee-ppm-limit",
        type=int,
        help="If set, only consider rebalance transactions that cost up to the given number of satoshis per "
             "1M satoshis sent. Note that the first hop costs are considered, even though you don't have to pay them."
    )
    return parser


def get_local_available(channel):
    return max(0, channel.local_balance - channel.local_chan_reserve_sat)


def get_remote_available(channel):
    return max(0, channel.remote_balance - channel.remote_chan_reserve_sat)


def get_local_ratio(channel):
    remote = channel.remote_balance
    local = channel.local_balance
    return (float(local) / (remote + local)) * 100


def get_capacity_and_ratio_bar(candidate, max_channel_capacity):
    columns = get_columns()
    columns_scaled_to_capacity = int(
        round(columns * float(candidate.capacity) / max_channel_capacity)
    )
    if candidate.capacity >= max_channel_capacity:
        columns_scaled_to_capacity = columns

    bar_width = columns_scaled_to_capacity - 2
    ratio = get_local_ratio(candidate)
    length = int(round(ratio * bar_width))
    return print_bar(bar_width, length)


def get_columns():
    if platform.system() == "Linux" and sys.__stdin__.isatty():
        return int(os.popen("stty size", "r").read().split()[1])
    else:
        return 80


def get_fee_adjusted(_ratio, _btc_fee):
    if _btc_fee > 140: # red
        coeff1 = 100
        coeff2 = 12.5
        coeff3 = 199
    elif _btc_fee > 80: #yellow
        coeff1 = 100
        coeff2 = 14.3
        coeff3 = 99
    elif _btc_fee > 20: #green
        coeff1 = 75
        coeff2 = 10.3
        coeff3 = 49
    else: #blue
        coeff1 = 49
        coeff2 = 6
        coeff3 = 1
        
    new_fee = (((coeff1 - _ratio) ** 2 ) / coeff2) + coeff3
    if new_fee < coeff3:
        new_fee = coeff3;
    if _ratio > coeff1:
        new_fee = coeff3;
    return (new_fee * fee_adjust)


success = main()
if success:
    sys.exit(0)
sys.exit(1)
