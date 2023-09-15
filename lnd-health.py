#!/usr/bin/env python3

import os
import logging
import subprocess
import time
import sys
from datetime import datetime, timedelta
import json

from output import format_alias_red, format_boring_string, format_amount_red_s

script_path = os.path.dirname(sys.argv[0])
logging.basicConfig(filename=script_path+"/lnd-health.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)

command = "/usr/local/bin/lncli getinfo"
result = json.loads(subprocess.check_output(command, shell = True))
current_height = result['block_height']
print(format_boring_string("Current Height: ") + str(current_height))

command = "/usr/local/bin/lncli listchannels"
result = json.loads(subprocess.check_output(command, shell = True))
i = 0
min_blocks_to_expire = 50000
min_alias = ""
for channel in result['channels']:
    alias = channel['peer_alias']
    active = channel['active']
    for pending_htlc in channel['pending_htlcs']:
        expiration_height = pending_htlc['expiration_height']
        blocks_to_expire = expiration_height - current_height
        if blocks_to_expire < min_blocks_to_expire:
            if active:
                min_blocks_to_expire = blocks_to_expire
                min_alias = alias
        
        if not active:
            formatted_active = f'{format_alias_red(str(active)):>5}'
        else:
            formatted_active = f'{str(active):>5}'
            
        #formatted_blocks_to_expire = f'{str(format_amount_red_s(blocks_to_expire,0)):>4}'
        formatted_blocks_to_expire = format_alias_red(f'{str(blocks_to_expire):>4}')
        
                
        #print(alias + " - expire: " + str(pending_htlc['expiration_height']) + " (" + str(blocks_to_expire) + "), active: " + str(active))
        print(format_boring_string("Expire: ") + str(pending_htlc['expiration_height']) + " (" + formatted_blocks_to_expire + ") | " + format_boring_string("Active: ") + formatted_active + " | " + format_boring_string("Node: ") + alias)
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
    print(" ")
print(format_boring_string("Pending HTLCs: ") + str(i) + " | " + format_boring_string("Min blocks to expire: ") + format_alias_red(str(min_blocks_to_expire)) + format_boring_string(" on ") + min_alias)

#print(channels)
#end_time = datetime.now()
#logging.error('some error')
#logging.debug('some debug')
        
#logging.info("Rebalancing finished")