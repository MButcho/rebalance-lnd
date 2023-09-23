import argparse

def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    
    test = "something "
    print(test.strip() + "cool")
    if arguments.command == "bos":
        if arguments.run:
            print("running bos command with --run")
        elif arguments.list:
            print("running bos command with --list")
        else:
            print(argument_parser.format_help())
    if arguments.command == "disk":
        print("running disk command")
    if arguments.command == "rebalances":
        print("running rebalances command")
        if arguments.list:
            print("running rebalances command with --list")
    if arguments.command == "htlcs":
        print("running htlcs command")
    
    
    
def get_argument_parser():
    parent_parser = argparse.ArgumentParser(description="The main script")
    subparsers = parent_parser.add_subparsers(title="commands", dest="command")
    parser_bos = subparsers.add_parser("bos", add_help=True, help="run bos rebalances")
    group_bos = parser_bos.add_mutually_exclusive_group()
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
    parser_rebalances = subparsers.add_parser("rebalances", add_help=True, help="show past rebalances")
    group_rebalances = parser_rebalances.add_mutually_exclusive_group()
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
    parser_htlcs = subparsers.add_parser("htlcs", add_help=True, help="show pending HTLCs")
    group_htlcs = parser_htlcs.add_argument_group()                                      
    group_htlcs.add_argument(
        "-t",
        "--telegram",
        action='store_true', 
        help="output in telegram format",
    )
    return parent_parser
    
success = main()