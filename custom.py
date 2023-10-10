#!/usr/bin/env python3

import os, tempfile
import logging
import subprocess
import time
import sys
import argparse
import re
from datetime import datetime, timedelta
from yachalk import chalk
import json
import collections, functools, operator
import random

from output import format_alias_red, format_boring_string, format_amount_red_s, format_amount_green, format_amount_red
mbsats4all = "02e38fd514a17b976cdbeddaf10bf4d0c3ee3211791d353cb755c9237189a91b96"

pid = os.getpid()
dir_path = os.path.dirname(sys.argv[0])
script_path = os.path.abspath(__file__)

def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    
    b_start = ""
    b_end = ""
    u_start = ""
    u_end = ""
    i_start = ""
    i_end = ""
    if arguments.telegram:
        b_start = "<b>"
        b_end = "</b>"
        u_start = "<u>"
        u_end = "</u>"
        i_start = "<i>"
        i_end = "</i>"
    
    if arguments.command == "bos":
        minutes = 30
        amount = 3000 * 1000
            
        if arguments.run:
            #max_time = 180 # max script run time
            #minutes = round(max_time / len(vampires)) - 1
            bos_file_path = dir_path+'/bos.conf'
            bos_tags_path = os.path.expanduser("~")+"/.bos/tags.json"
            logging.basicConfig(filename=dir_path+"/bos.log", format='%(asctime)s [%(levelname)s] (' + str(pid) + ') %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
            logging.info("Rebalancing started (" + str(minutes) + " mins)")

            bos_file = open(bos_file_path, 'r')
            vampires_l = bos_file.read().split('\n')
            bos_file.close()
            vampires = [x for x in vampires_l if x != '']

            for str_line in vampires:
                if str_line != "":
                    str_line_arr = str_line.split(';')
                    alias = str_line_arr[0]
                    own_ppm = round(int(str_line_arr[1]))
                    ratio = round(float(str_line_arr[2]))
                    events = round(int(str_line_arr[3]))
                    
                    target_ratio = 7.5+(ratio/15) # check https://www.desmos.com/calculator
                    #target_ratio = 10-(ratio/7.5) # check https://www.desmos.com/calculator
                    event_ratio = 1.5-(events/20) # check https://www.desmos.com/calculator
                    if event_ratio < 1:
                        event_ratio = 1
                    target_ratio = target_ratio/event_ratio
                    target_ppm = round(own_ppm*((100-target_ratio)/100))
                    fee_delta = own_ppm - target_ppm
                    
                    # sources
                    _sources_arr = []
                    try:
                        #source_i = random.randint(0,2)
                        _sources = json.load(open(bos_tags_path))
                        for _tag in _sources['tags']:
                            if _tag['alias'] == "sources":
                                for _source in _tag['nodes']:
                                    _sources_arr.append(_source)
                                    
                        random.shuffle(_sources_arr)
                    except:
                        _sources_arr.append("sources")
                    
                    delta_min = 0
                    for _source in _sources_arr:
                        if delta_min == 0:
                            source = get_listchannels('peer_alias', _source)
                            start_time = datetime.now()        
                            logging.info(alias + " started via " + source + " (a: " + str(round(amount/1000)) + "k, t: " + str(target_ppm) + "(-" + str(fee_delta) + "/-" + str(round(target_ratio,1)) + "%), e: " + str(events) + ")")
                            
                            temp = tempfile.NamedTemporaryFile()
                            os.chmod(temp.name, 0o644)
                            command = "/usr/bin/bos rebalance --in '" + alias + "' --out '" + source + "' --max-fee-rate " + str(target_ppm) + " --max-fee 5000 --avoid-high-fee-routes --avoid vampires --minutes " + str(minutes) + " --amount " + str(amount) + " >> " + temp.name
                            #source = "N/A"
                            result = os.system(command)
                            try:
                                output = temp.read().decode('utf-8')
                                # regex = re.search("(?<=outgoing_peer_to_increase_inbound: ).*", output)
                                # if regex != None:                    
                                    # source_arr = regex.group(0).split(" ")
                                    # source = ""
                                    # for x in range(0, len(source_arr)-1):
                                        # source += source_arr[x] + " "
                            except:
                                output = "N/A"
                            end_time = datetime.now()
                            delta_min = round((end_time - start_time).total_seconds() / 60)
                            if delta_min < minutes:
                                formatted_mins = chalk.red(str(delta_min) + " mins")
                            else:
                                formatted_mins = chalk.green(str(delta_min) + " mins")
                            logging.info(alias + " via " + source.strip() + " finished in " + formatted_mins + " (" + str(result) + ")")
                            if delta_min == 0:
                                rebalance_err_file = open(dir_path+"/rebalance_err.log", 'a')
                                rebalance_err_file.write(end_time.strftime("%Y-%m-%d %H:%M:%S"))
                                rebalance_err_file.write(output)
                                rebalance_err_file.close()
                            if delta_min < 10:
                                delta_min = 0 # to continue next source
                    time.sleep(30)
                    #logging.error('some error')
                    #logging.debug('some debug')
                    
            logging.info("Rebalancing finished")
        elif arguments.list:
            command = "ps -ef | grep 'sh -c /usr/bin/bos'"
            result = subprocess.check_output(command, shell = True).decode(sys.stdout.encoding)
            procs_arr = re.findall("(?<=sh -c \/usr\/bin\/).*?(?= >>)", result)
            tmp_arr = re.findall("(?<=>> ).*", result)
            i = 0
            print("☯ Running (" + b_start + str(len(procs_arr)) + b_end + ") bos rebalances (" + b_start + str(minutes) + " mins" + b_end + ")")
            for _procs in procs_arr:
                source = "N/A"
                try:
                    tmp_file = open(tmp_arr[i], 'r')
                    output = tmp_file.read()
                    tmp_file.close()
                    regex = re.search("(?<=outgoing_peer_to_increase_inbound: ).*", output)
                    if regex != None:                    
                        source_arr = regex.group(0).split(" ")
                        source = ""
                        for x in range(0, len(source_arr)-1):
                            source += source_arr[x] + " "
                except:
                    source = "N/A"
                
                #print("Source: " + b_start + source.strip() + b_end + " | " + _procs)
                print(b_start + str(i+1) + ". " + b_end + _procs)
                i+=1
            
    elif arguments.command == "disk":
        command = "df -h"
        result = subprocess.check_output(command, shell = True).decode(sys.stdout.encoding)
        lines = result.split("\n")
        for _line in lines:
            regex = re.search(".*\/$", _line)
            if regex != None:
                #_output_arr = regex.group(0).split(" ")
                _output_arr = [x for x in regex.group(0).split(" ") if x != '']
                fs = _output_arr[0]
                size = _output_arr[1]
                used = _output_arr[2]
                avail = _output_arr[3]
                use = _output_arr[4]
                free = 100-int(use[:-1])
                mounted = _output_arr[5]                
                print("🖥 " + avail + " (" + b_start + str(free) + b_end + "%) free of " + size + " disk mounted on " + mounted)
    
    elif arguments.command == "earn":
        interval = arguments.days
        from_interval = int(round((datetime.now() - timedelta(days=interval)).timestamp()))
        command = "/usr/local/bin/lncli fwdinghistory --start_time " + str(from_interval) + " --max_events 50000"
        result = json.loads(subprocess.check_output(command, shell = True))
        fw_fees_interval = round(sum(map(lambda x: int(x['fee_msat']), result['forwarding_events']))/1000)
        
        from_24h = int(round((datetime.now() - timedelta(days=1)).timestamp()))
        command = "/usr/local/bin/lncli fwdinghistory --start_time " + str(from_24h) + " --max_events 50000"
        result = json.loads(subprocess.check_output(command, shell = True))
        fw_fees_24h = round(sum(map(lambda x: int(x['fee_msat']), result['forwarding_events']))/1000)
        
        command = script_path + " rebalances -f -d 1"
        r_fees_24 = int(subprocess.check_output(command, shell = True).decode(sys.stdout.encoding))
        
        command = script_path + " rebalances -f -d " + str(interval)
        r_fees_interval = int(subprocess.check_output(command, shell = True).decode(sys.stdout.encoding))
        
        if arguments.telegram:
            print("💰 Earnings • 24h: " + b_start + str(fw_fees_24h-r_fees_24) + b_end + " • " + str(interval) + "d: " + b_start + str(fw_fees_interval-r_fees_interval) + b_end)
            print("Forwarding fees • 24h: " + b_start + str(fw_fees_24h) + b_end + " • " + str(interval) + "d: " + b_start + str(fw_fees_interval) + b_end)
            print("Rebalances fees • 24h: -" + b_start + str(r_fees_24) + b_end + " • " + str(interval) + "d: -" + b_start + str(r_fees_interval) + b_end)
        else:
            print(format_boring_string("Forwarding fees") + " | " + format_boring_string("24h: ") + format_amount_green(fw_fees_24h,9) + " | " + format_boring_string(str(interval) + "d: ") + format_amount_green(fw_fees_interval,9))
            print(format_boring_string("Rebalances fees") + " | " + format_boring_string("24h: ") + format_amount_red(-r_fees_24,9) + " | " + format_boring_string(str(interval) + "d: ") + format_amount_red(-r_fees_interval,9))
            print(format_boring_string("Total earnings ") + " | " + format_boring_string("24h: ") + (format_amount_green(fw_fees_24h-r_fees_24,9) if (fw_fees_24h-r_fees_24) > 0 else format_amount_red(fw_fees_24h-r_fees_24,9)) + " | " + format_boring_string(str(interval) + "d: ") + (format_amount_green(fw_fees_interval-r_fees_interval,9) if fw_fees_interval-r_fees_interval > 0 else format_amount_red(fw_fees_interval-r_fees_interval,9)))
            
    elif arguments.command == "htlcs":
        logging.basicConfig(filename=dir_path+"/lnd-htlcs.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
        command = "/usr/local/bin/lncli getinfo"
        result = json.loads(subprocess.check_output(command, shell = True))
        current_height = result['block_height']

        i = 0
        min_blocks_to_expire = 50000
        min_alias = ""
        all_htlcs = ""
        all_amount = 0
        arr_htlcs = []
        for _channel in get_listchannels('channels', ""):
            alias = _channel['peer_alias']
            active = _channel['active']
            chan_point = _channel['channel_point']
            for pending_htlc in _channel['pending_htlcs']:
                amount = pending_htlc['amount']
                all_amount += int(amount)
                expiration_height = pending_htlc['expiration_height']
                blocks_to_expire = expiration_height - current_height
                if blocks_to_expire < min_blocks_to_expire:
                    if active:
                        min_blocks_to_expire = blocks_to_expire
                        min_alias = alias
                        #fee wall
                        if blocks_to_expire < 35:
                            command = "lncli updatechanpolicy --base_fee_msat 0 --time_lock_delta 100 --fee_rate_ppm 2500 --chan_point " + chan_point
                            result_wall = subprocess.check_output(command, shell = True).decode(sys.stdout.encoding)
                
                if len(pending_htlc) > 0:
                    arr_htlcs.append({'alias':alias, 'active':active, 'expiration_height':expiration_height, 'blocks_to_expire':blocks_to_expire, 'amount': amount})
                    i+=1

        if i == 0 or min_blocks_to_expire == 50000:
            min_blocks_to_expire = 144
            min_alias = "N/A"

        try:
            zabbix_pending_count = open("/tmp/lnd-pending-count", 'w')
            zabbix_pending_count.write(str(i))
            zabbix_pending_count.close()

            zabbix_pending_min = open("/tmp/lnd-pending-min", 'w')
            zabbix_pending_min.write(str(min_blocks_to_expire))
            zabbix_pending_min.close()

            logging.info("Pending HTLCs: Total = " + str(i) + ", Min blocks to expire = " + str(min_blocks_to_expire) + " on " + min_alias)
        except:
            print("")
        
        if arguments.list and arguments.telegram == False:
            print(format_boring_string("Current Height: ") + str(current_height))
            arr_htlcs_sorted = sorted(arr_htlcs, key = lambda item:item['blocks_to_expire'], reverse = True)
            for _htlc in arr_htlcs_sorted:
                formatted_blocks_to_expire = format_alias_red(f'{str(_htlc["blocks_to_expire"]):>4}')
                formatted_amount = format_amount_green(int(_htlc["amount"]),9)
                if not _htlc["active"]:
                    formatted_alias = format_alias_red(_htlc['alias'])
                else:
                    formatted_alias = _htlc['alias']
                print(format_boring_string("Expire: ") + str(_htlc["expiration_height"]) + " (" + formatted_blocks_to_expire + ") | " + format_boring_string("Amount: ") + formatted_amount + " | " + format_boring_string("Node: ") + formatted_alias)
            print(format_boring_string("Pending HTLCs: ") + str(i) + " | " + format_boring_string("Min blocks to expire: ") + format_alias_red(str(min_blocks_to_expire)) + format_boring_string(" on ") + min_alias + " | " + format_boring_string("Total: ") + format_amount_green(all_amount,0) + format_boring_string(" sats"))
        if arguments.telegram:
            print("⏳ " + b_start + str(i) + b_end + " pending HTLCs (min. " + b_start + str(min_blocks_to_expire) + b_end + " on " + b_start + min_alias + b_end + ") for <i>" + format_amount_green(all_amount,0) + "</i>")
            arr_htlcs_sorted = sorted(arr_htlcs, key = lambda item:item['blocks_to_expire'], reverse = False)
            for _htlc in arr_htlcs_sorted:
                formatted_blocks_to_expire = format_alias_red(f'{str(_htlc["blocks_to_expire"]):>4}')
                formatted_amount = format_amount_green(int(_htlc["amount"]),0)
                if not _htlc["active"]:
                    formatted_alias = format_alias_red(_htlc['alias'])
                else:
                    formatted_alias = _htlc['alias']
                status = ""
                amount = f'{int(_htlc["amount"]):,}'
                if not _htlc['active']:
                    status = " (I)"
                print(b_start + str(formatted_blocks_to_expire) + b_end + " blocks on " + b_start + formatted_alias + status + b_end + " for " + i_start + str(formatted_amount) + i_end + " sats")
            print(i_start + "Current Height: " + b_start + str(current_height) + b_end + i_end)
            
    elif arguments.command == "rebalances":
        #logging.basicConfig(filename=dir_path+"/lnd-health.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
        summary_from = []
        summary_to = []
        
        interval = arguments.days
        from_interval = int(round((datetime.now() - timedelta(days=interval)).timestamp()))

        chan_ids = []
        peer_aliases = []
        for _channel in get_listchannels('channels', ""):
            chan_ids.append(_channel['chan_id'])
            peer_aliases.append(_channel['peer_alias'])

        command = "/usr/local/bin/lncli listpayments --creation_date_start " + str(from_interval)
        result = json.loads(subprocess.check_output(command, shell = True))
        i = 0
        fees = 0
        value = 0

        for payment in result['payments']:
            payment_request = payment['payment_request']
            value_sat = payment['value_sat']
            status = payment['status']
            creation_date = payment['creation_date']
            if payment_request == "" and status == "SUCCEEDED":        
                for htlc in payment['htlcs']:
                    route = htlc['route']
                    total_fees_msat = route['total_fees_msat']
                    h = 0
                    for hop in route['hops']:
                        if h == 0:
                            chan_from = hop['chan_id']
                            try:
                                x = chan_ids.index(chan_from)
                                peer_from = peer_aliases[x]                            
                            except:
                                peer_from = chan_from
                        if h == len(route['hops'])-1:
                            chan_to = hop['chan_id']
                            mpp_record = hop['mpp_record']
                            try:
                                x = chan_ids.index(chan_to)
                                peer_to = peer_aliases[x]
                            except:
                                peer_to = chan_to
                            #print(mpp_record)
                        h+=1
                date = datetime.fromtimestamp(int(creation_date)).strftime('%Y-%m-%d %H:%M:%S')
                if mpp_record is not None:
                    i+=1
                    summary_from.append({peer_from: int(value_sat)})
                    summary_to.append({peer_to: int(value_sat)})
                    fees+=int(total_fees_msat)/1000
                    value+=int(value_sat)
                    if arguments.list:
                        print(format_boring_string(date) + " • " + peer_from + " -> " + peer_to + " • " + format_boring_string("Amount: ") + str(format_amount_green(int(value_sat),0)) + " • " + format_boring_string("Fee: ") + str(format_amount_red(round(int(total_fees_msat)/1000),0)))
        
        if arguments.count == False and arguments.fees == False:
            print(format_boring_string("☯️ Rebalances count (" + str(interval) + " days): ") + b_start + format_amount_red_s(str(i),0) + b_end + " • " + format_boring_string("Value: ") + b_start + i_start + str(format_amount_green(round(int(value)),0)) + i_end + b_end + " • " + format_boring_string("Fees: ") + i_start + str(format_amount_red(round(fees),0)) + i_end)
        
        if arguments.summary:
            print(format_boring_string(b_start + u_start + "Sources (from):" + u_end + b_end))
            summary_from_sorted = sorted(dict(functools.reduce(operator.add, map(collections.Counter, summary_from))).items(), key = lambda x:x[1], reverse = True)
            for _peer, _value in summary_from_sorted:
                print(i_start + str(format_amount_red(_value,0)) + i_end + " ← " + _peer)
            print(format_boring_string(b_start + u_start + "Vampires (to):" + u_end + b_end))
            summary_to_sorted = sorted(dict(functools.reduce(operator.add, map(collections.Counter, summary_to))).items(), key = lambda x:x[1], reverse = True)
            for _peer, _value in summary_to_sorted:
                print(i_start + str(format_amount_green(_value,0)) + i_end + " → " + _peer)
        if arguments.count:
            _count = 0
            if arguments.node == "all":
                print(len(summary_to))
            elif arguments.node == "list":
                print(json.dumps(summary_to))
            else:
                for _summary in summary_to:
                    if arguments.node in _summary:
                        _count+=1
                print(_count)
        if arguments.fees:
            print(round(fees))
    elif arguments.command == "reconnect":
        command = "/usr/bin/bos reconnect"
        result = subprocess.check_output(command, shell = True).decode(sys.stdout.encoding)
        result_arr = result.split("\n")
        offline = []
        reconnected = []
        delimiter = ', '
        i = 0
        for _result in result_arr:
            if "reconnected" in _result:
                i = 1
            _alias = re.search("(?<=alias: ).*", _result)
            if _alias != None: 
                if i == 0:
                    offline.append(_alias.group(0).strip())
                else:
                    reconnected.append(_alias.group(0).strip())
        
        if len(offline) == 0:
            offline.append("None")
            icon = "🟢 "
        else:
            icon = "🔴 "
            
        if len(reconnected) == 0:
            reconnected.append("None")
        
        print(icon + b_start + "Offline: " + b_end + delimiter.join(offline))
        print(b_start + "Reconnected: " + b_end + delimiter.join(reconnected))
    else:
        sys.exit(argument_parser.format_help())

def get_listchannels(_field, _public_key):
    command = "/usr/local/bin/lncli listchannels"
    listchannels = json.loads(subprocess.check_output(command, shell = True))
    
    if _public_key != "":
        _result = "N/A"
        for _channel in listchannels['channels']:
            if _channel['remote_pubkey'] == _public_key:
                _result = _channel[_field]
        return _result
    elif _field == "channels":
        return listchannels['channels']
    
   
def get_argument_parser():
    parent_parser = argparse.ArgumentParser(description="The main script")
    parent_parser.add_argument(
        "-t",
        "--telegram",
        action='store_true', 
        help="output in telegram format",
    )
    subparsers = parent_parser.add_subparsers(title="commands", dest="command")
    parser_bos = subparsers.add_parser("bos", add_help=True, help="run bos rebalances")
    group_bos = parser_bos.add_mutually_exclusive_group(required=True)
    group_bos.add_argument(
        "-l", 
        "--list", 
        action='store_true', 
        help="show running bos rebalances"
    )
    group_bos.add_argument(
        "-r",
        "--run",
        action='store_true', 
        help="run bos rebalances",
    )
    parser_disk = subparsers.add_parser("disk", add_help=False, help="show free disk space")
    parser_earn = subparsers.add_parser("earn", add_help=True, help="show earnings (forwards - rebalances)")
    parser_earn.add_argument(
        "-d",
        "--days",
        type=int,
        default=7,
        help="interval in days (default: 7)",
    )
    parser_forwards = subparsers.add_parser("forwards", add_help=True, help="show forwards)")
    parser_forwards.add_argument(
        "-d",
        "--days",
        type=int,
        default=7,
        help="interval in days (default: 7)",
    )
    parser_htlcs = subparsers.add_parser("htlcs", add_help=True, help="show pending HTLCs")
    group_htlcs = parser_htlcs.add_argument_group() 
    group_htlcs.add_argument(
        "-l", 
        "--list",
        #required=True,
        action='store_true', 
        help="show list of rebalances"
    )
    parser_rebalances = subparsers.add_parser("rebalances", add_help=True, help="show past rebalances")
    group_rebalances = parser_rebalances.add_mutually_exclusive_group(required=True)
    group_rebalances.add_argument(
        "-c", 
        "--count", 
        action='store_true', 
        help="show count of rebalances"
    )
    group_rebalances.add_argument(
        "-f",
        "--fees",
        action='store_true',
        help="show fees for rebalances",
    )
    group_rebalances.add_argument(
        "-l", 
        "--list", 
        action='store_true', 
        help="show list of rebalances"
    )
    group_rebalances.add_argument(
        "-s",
        "--summary",
        action='store_true', 
        help="show summary of rebalances",
    )
    parser_rebalances.add_argument(
        "-d",
        "--days",
        type=int,
        default=7,
        help="interval in days (default: 7)",
    )    
    parser_rebalances.add_argument(
        "-n", 
        "--node",
        default="all",
        help="show count of rebalances"
    )
    parser_reconnect = subparsers.add_parser("reconnect", add_help=False, help="run bos reconnect")
    return parent_parser
    
success = main()