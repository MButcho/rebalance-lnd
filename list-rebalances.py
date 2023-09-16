#!/usr/bin/env python3

import os
import logging
import subprocess
import time
import sys
from datetime import datetime, timedelta
import json

from output import format_alias_red, format_boring_string, format_amount_red_s
mbsats4all = "02e38fd514a17b976cdbeddaf10bf4d0c3ee3211791d353cb755c9237189a91b96"

script_path = os.path.dirname(sys.argv[0])
#logging.basicConfig(filename=script_path+"/lnd-health.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)

time = datetime.now()
from_7d = int(round((time - timedelta(days=7)).timestamp()))

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

for payment in result['payments']:
    payment_request = payment['payment_request']
    value_sat = payment['value_sat']
    status = payment['status']
    creation_date = payment['creation_date']
    if payment_request == "" and status == "SUCCEEDED" and int(creation_date) > from_7d:
    
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
            fees+=int(total_fees_msat)/1000            
            print(peer_from + " -> " + peer_to + ", amount: " + str(value_sat) + ", fee: " + str(round(int(total_fees_msat)/1000,3)) + ", date: " + date)

print("Rebalance in last 7 days: " + str(i) + " | Fees: " + str(round(fees,3)))