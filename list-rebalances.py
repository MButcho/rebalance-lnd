#!/usr/bin/env python3

import argparse
import os
import logging
import subprocess
import time
import sys
from datetime import datetime, timedelta
import json
import collections, functools, operator

from output import format_alias_red, format_boring_string, format_amount_red_s, format_amount_green, format_amount_red
mbsats4all = "02e38fd514a17b976cdbeddaf10bf4d0c3ee3211791d353cb755c9237189a91b96"

script_path = os.path.dirname(sys.argv[0])
#logging.basicConfig(filename=script_path+"/lnd-health.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)

def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    summary_from = []
    summary_to = []
    
    interval = arguments.days 
    #print(arguments.summary)
    #print(arguments.list)

    time = datetime.now()
    from_interval = int(round((time - timedelta(days=interval)).timestamp()))

    command = "/usr/local/bin/lncli listchannels"
    channels_json = json.loads(subprocess.check_output(command, shell = True))
    chan_ids = []
    peer_aliases = []
    for channel in channels_json['channels']:
        chan_ids.append(channel['chan_id'])
        peer_aliases.append(channel['peer_alias'])

    command = "/usr/local/bin/lncli listpayments"
    result = json.loads(subprocess.check_output(command, shell = True))
    i = 0
    fees = 0
    value = 0

    for payment in result['payments']:
        payment_request = payment['payment_request']
        value_sat = payment['value_sat']
        status = payment['status']
        creation_date = payment['creation_date']
        if payment_request == "" and status == "SUCCEEDED" and int(creation_date) > from_interval:        
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
                    print(format_boring_string(date) + " | " + peer_from + " -> " + peer_to + " | " + format_boring_string("Amount: ") + str(format_amount_green(int(value_sat),0)) + " | " + format_boring_string("Fee: ") + str(format_amount_red_s(round(int(total_fees_msat)/1000,3),3)))

    print(format_boring_string("Rebalances count (" + str(interval) + " days): ") + format_amount_red_s(str(i),0) + " | " + format_boring_string("Value: ") + str(format_amount_green(round(int(value)),0)) + " | " + format_boring_string("Fees: ") + str(format_amount_red_s(round(fees,3),3)))
    
    if arguments.summary:
        print(format_boring_string("Sources (from):"))
        summary_from_sorted = sorted(dict(functools.reduce(operator.add, map(collections.Counter, summary_from))).items(), key = lambda x:x[1], reverse = True)
        for _peer, _value in summary_from_sorted:
            print(str(format_amount_red(_value,0)) + " ← " + _peer)
        print(format_boring_string("Vampires (to):"))
        summary_to_sorted = sorted(dict(functools.reduce(operator.add, map(collections.Counter, summary_to))).items(), key = lambda x:x[1], reverse = True)
        for _peer, _value in summary_to_sorted:
            print(str(format_amount_green(_value,0)) + " → " + _peer)
    
def get_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-l",
        "--list",
        action='store_true', 
        help="Print list of rebalances",
    )
    parser.add_argument(
        "-d",
        "--days",
        type=int,
        default=7,
        help="Interval in days (default: 7)",
    )
    parser.add_argument(
        "-s",
        "--summary",
        action='store_true', 
        help="Print summary of rebalances",
    )
    return parser
    
success = main()