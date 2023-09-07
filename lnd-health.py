#!/usr/bin/env python3

import os
import logging
import subprocess
import time
import sys
from datetime import datetime, timedelta
import json

script_path = os.path.dirname(sys.argv[0])
logging.basicConfig(filename=script_path+"/lnd-health.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)

command = "/usr/local/bin/bitcoin-cli getblockchaininfo"
result = json.loads(subprocess.check_output(command, shell = True))
current_height = result['blocks']
print("Current Height: " + str(current_height))

command = "/usr/local/bin/lncli listchannels"
result = json.loads(subprocess.check_output(command, shell = True))
i = 0
min_blocks_to_expire = 50000
min_alias = ""
for channel in result['channels']:
    alias = channel['peer_alias']
    for pending_htlc in channel['pending_htlcs']:
        expiration_height = pending_htlc['expiration_height']
        blocks_to_expire = expiration_height - current_height
        if blocks_to_expire < min_blocks_to_expire:
            min_blocks_to_expire = blocks_to_expire
            min_alias = alias
        print(alias + " - Expire: " + str(pending_htlc['expiration_height']) + " (" + str(blocks_to_expire) + ")")
        i+=1

if i == 0:
    min_blocks_to_expire = 144

zabbix_pending_count = open("/tmp/lnd-pending-count", 'w')
zabbix_pending_count.write(str(i))
zabbix_pending_count.close()

zabbix_pending_min = open("/tmp/lnd-pending-min", 'w')
zabbix_pending_min.write(str(min_blocks_to_expire))
zabbix_pending_min.close()

logging.info("Pending HTLCs: Total = " + str(i) + ", Min blocks to expire = " + str(min_blocks_to_expire) + " on " + min_alias)

#print(channels)
#end_time = datetime.now()
#logging.error('some error')
#logging.debug('some debug')
        
#logging.info("Rebalancing finished")