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

pid = os.getpid()
script_path = os.path.dirname(sys.argv[0])
bos_file_path = script_path+'/bos.conf'
logging.basicConfig(filename=script_path+"/bos.log", format='%(asctime)s [%(levelname)s] (' + str(pid) + ') %(message)s', datefmt='%Y/%m/%d %H:%M:%S', level=logging.INFO)
#max_time = 180 # max script run time
#minutes = round(max_time / len(vampires)) - 1
minutes = 30
amount = 3000 * 1000

def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    
    if arguments.rebalance:
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
                
                start_time = datetime.now()        
                logging.info(alias + " started (a: " + str(round(amount/1000)) + "k, t: " + str(target_ppm) + "(-" + str(fee_delta) + "/-" + str(round(target_ratio,1)) + "%), e: " + str(events) + ")")
                
                temp = tempfile.NamedTemporaryFile()
                os.chmod(temp.name, 0o644)
                #command = "/usr/bin/bos rebalance --in '" + alias + "' --out sources --max-fee-rate " + str(target_ppm) + " --max-fee 5000 --avoid-high-fee-routes --avoid vampires --minutes " + str(minutes) + " --amount " + str(amount) + " >> " + script_path + "/bos_raw.log"
                command = "/usr/bin/bos rebalance --in '" + alias + "' --out sources --max-fee-rate " + str(target_ppm) + " --max-fee 5000 --avoid-high-fee-routes --avoid vampires --minutes " + str(minutes) + " --amount " + str(amount) + " >> " + temp.name
                result = os.system(command)
                output = temp.read().decode('utf-8')
                #output_arr = re.search("(?<=outgoing_peer_to_increase_inbound: ).*", output)
                output_arr = re.findall("(?<=outgoing_peer_to_increase_inbound: ).*", output)
                #print(source.string)
                for _output in output_arr:
                    source_arr = _output.split(" ")
                    source = source_arr[0]
                end_time = datetime.now()
                delta_min = round((end_time - start_time).total_seconds() / 60)
                if delta_min < minutes:
                    formatted_mins = chalk.red(str(delta_min) + " mins")
                else:
                    formatted_mins = chalk.green(str(delta_min) + " mins")
                logging.info(alias + " from " + source + " finished in " + formatted_mins + " (" + str(result) + ")")
                time.sleep(30)
                #logging.error('some error')
                #logging.debug('some debug')
                
        logging.info("Rebalancing finished")
        
    if arguments.list:
        command = "ps -ef | grep 'sh -c /usr/bin/bos'"
        result = subprocess.check_output(command, shell = True).decode(sys.stdout.encoding)
        procs_arr = re.findall("(?<=sh -c \/usr\/bin\/).*?(?= >>)", result)
        tmp_arr = re.findall("(?<=>> ).*", result)
        i = 0
        print("☯ Running (" + str(len(procs_arr)) + ") bos rebalances")
        for _procs in procs_arr:
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
            
            print(_procs + " | source: " + source)
            i+=1
            
    if arguments.disk:
        command = "df -h"
        result = subprocess.check_output(command, shell = True).decode(sys.stdout.encoding)
        lines = result.split("\n")
        for _line in lines:
            regex = re.search(".*\/$", _line)
            if regex != None:
                _output_arr = regex.group(0).split(" ")
                _output_arr = [x for x in _output_arr if x != '']
                print(_output_arr)
                fs = _output_arr[0]
                size = _output_arr[1]
                used = _output_arr[2]
                avail = _output_arr[3]
                use = _output_arr[4]
                free = 100-int(use[:-1])
                mounted = _output_arr[5]                
                print("🖥 " + avail + " (" + str(free) + "%) free of " + size + " disk mounted on " + mounted)
    
def get_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--disk",
        action='store_true', 
        help="Print free disk space",
    )
    parser.add_argument(
        "-l",
        "--list",
        action='store_true', 
        help="Print running rebalances",
    )
    parser.add_argument(
        "-r",
        "--rebalance",
        action='store_true', 
        help="Run bos rebalances",
    )
    return parser
    
success = main()