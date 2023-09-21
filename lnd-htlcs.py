#!/usr/bin/env python3

import argparse
import os
import logging
import subprocess
import time
import sys
from datetime import datetime, timedelta
import json

from output import format_alias_red, format_boring_string, format_amount_red_s, format_amount_green

script_path = os.path.dirname(sys.argv[0])
logging.basicConfig(filename=script_path+"/lnd-htlcs.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)

def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    
    command = "/usr/local/bin/lncli getinfo"
    result = json.loads(subprocess.check_output(command, shell = True))
    current_height = result['block_height']

    command = "/usr/local/bin/lncli listchannels"
    result = json.loads(subprocess.check_output(command, shell = True))
    i = 0
    min_blocks_to_expire = 50000
    min_alias = ""
    all_htlcs = ""
    arr_htlcs = []
    for channel in result['channels']:
        alias = channel['peer_alias']
        active = channel['active']
        for pending_htlc in channel['pending_htlcs']:
            amount = pending_htlc['amount']
            expiration_height = pending_htlc['expiration_height']
            blocks_to_expire = expiration_height - current_height
            if blocks_to_expire < min_blocks_to_expire:
                if active:
                    min_blocks_to_expire = blocks_to_expire
                    min_alias = alias
            
            if len(pending_htlc) > 0:
                arr_htlcs.append({'alias':alias, 'active':active, 'expiration_height':expiration_height, 'blocks_to_expire':blocks_to_expire, 'amount': amount})
                i+=1

    if i == 0:
        min_blocks_to_expire = 144

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
    
    if arguments.telegram:
        print("💰" + str(i) + " pending HTLCs (min. " + str(min_blocks_to_expire) + " on " + min_alias + ")")
        arr_htlcs_sorted = sorted(arr_htlcs, key = lambda item:item['blocks_to_expire'], reverse = False)
        for _htlc in arr_htlcs_sorted:
            status = ""
            amount = f'{int(_htlc["amount"]):,}'
            if not _htlc['active']:
                status = " (I)"
            print(str(_htlc['blocks_to_expire']) + " blocks on " + _htlc['alias'] + status + " for " + str(amount) + " sats")
        print("Current Height: " + str(current_height))
    else:
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
        print(format_boring_string("Pending HTLCs: ") + str(i) + " | " + format_boring_string("Min blocks to expire: ") + format_alias_red(str(min_blocks_to_expire)) + format_boring_string(" on ") + min_alias)

def get_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-g",
        "--telegram",
        action='store_true', 
        help="Output in Telegram format",
    )
    return parser
    
success = main()
#if success:
#    sys.exit(0)
#sys.exit(1)


#print(channels)
#end_time = datetime.now()
#logging.error('some error')
#logging.debug('some debug')
        
#logging.info("Rebalancing finished")