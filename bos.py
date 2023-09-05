#!/usr/bin/env python3

import os
import logging
import subprocess
import time
import sys
from datetime import datetime, timedelta

script_path = os.path.dirname(sys.argv[0])
bos_file_path = script_path+'/bos.conf'
bos_file = open(bos_file_path, 'r')
vampires_l = bos_file.read().split('\n')
vampires = [x for x in vampires_l if x != '']
logging.basicConfig(filename=script_path+"/bos.log", format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
max_time = 150 # max script run time
minutes = round(max_time / len(vampires)) - 1
logging.info("Rebalancing started")

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
        
        amount = 2500 * 1000
        
        start_time = datetime.now()        
        logging.info("Rebalancing " + alias + " started (a: " + str(round(amount/1000)) + "k, t: " + str(target_ppm) + "(-" + str(fee_delta) + "/-" + str(round(target_ratio,1)) + "%), e: " + str(events) + ")")
        command = "/usr/bin/bos rebalance --in '" + alias + "' --out sources --max-fee-rate " + str(target_ppm) + " --max-fee 5000 --avoid-high-fee-routes --avoid vampires --minutes " + str(minutes) + " --amount " + str(amount) + " >> " + script_path + "/bos_raw.log"
        result = os.system(command)
        end_time = datetime.now()
        delta_min = round((end_time - start_time).total_seconds() / 60)
        logging.info("Rebalancing " + alias + " finished in " + str(delta_min) + " mins (" + str(result) + ")")
        time.sleep(5)
        #logging.error('some error')
        #logging.debug('some debug')
        
logging.info("Rebalancing finished")