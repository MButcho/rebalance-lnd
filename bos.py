#!/usr/bin/env python3

import os
import logging
import subprocess
import time
from datetime import datetime, timedelta

bos_file_path = '/data/rebalance-lnd/bos.conf'
bos_file = open(bos_file_path, 'r')
vampires_l = bos_file.read().split('\n')
vampires = [x for x in vampires_l if x != '']
logging.basicConfig(filename="/home/lnd/.bos/bos.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
cron = 120 # running every 120 min
#minutes = 15
minutes = round(cron / len(vampires)) - 1
#minutes = round(((cron - len(vampires)) / len(vampires)) - 1)
logging.info("Rebalancing started")
#minutes = 1

for str_line in vampires:
    if str_line != "":
        str_line_arr = str_line.split(';')
        alias = str_line_arr[0]
        own_ppm = round(int(str_line_arr[1]))
        ratio = round(float(str_line_arr[2]))
        events = round(int(str_line_arr[3]))
        
        target_ratio = 10-(ratio/7.5) # check https://www.desmos.com/calculator
        event_ratio = 2-(events/5) # check https://www.desmos.com/calculator
        if event_ratio < 1:
            event_ratio = 1
        target_ratio = target_ratio/event_ratio
        target_ppm = round(own_ppm*((100-target_ratio)/100))
        fee_delta = own_ppm - target_ppm
        
        amount = 2500 * 1000
        
        start_time = datetime.now()        
        logging.info("Rebalancing " + alias + " started (amount: " + str(round(amount/1000)) + "k, target ppm: " + str(target_ppm) + "(-" + str(fee_delta) + "), events: " + str(events) + ")")
        command = "/usr/bin/bos rebalance --in '" + alias + "' --out sources --max-fee-rate " + str(target_ppm) + " --max-fee 5000 --avoid-high-fee-routes --avoid vampires --minutes " + str(minutes) + " --amount " + str(amount) + " >> /home/lnd/.bos/bos_raw.log"
        result = os.system(command)
        end_time = datetime.now()
        delta_min = round((end_time - start_time).total_seconds() / 60)
        logging.info("Rebalancing " + alias + " finished in " + str(delta_min) + " mins (" + str(result) + ")")
        time.sleep(5)
        #logging.error('some error')
        #logging.debug('some debug')
        
logging.info("Rebalancing finished")