import argparse

def main():
    argument_parser = get_argument_parser()
    arguments = argument_parser.parse_args()
    
def get_argument_parser():
    parent_parser = argparse.ArgumentParser()
    parent_parser.add_argument(
        "-d",
        "--disk",
        action='store_true', 
        help="Show free disk space",
    )
    parent_parser.add_argument(
        "-b",
        "--bos",
        action='store_true', 
        help="Run bos rebalances",
    )
    parent_parser.add_argument(
        "-r",
        "--rebalance",
        action='store_true', 
        help="Show past rebalances",
    )
    parent_parser.add_argument(
        "-p",
        "--htlc",
        action='store_true', 
        help="Show pending HTLCs",
    )
    
    bos_group = parent_parser.add_argument_group('bos')
    bos_group.add_argument(
        "-l",
        "--list",
        action='store_true', 
        help="Show running bos rebalances",
    )
    bos_group.add_argument(
        "-r",
        "--run",
        action='store_true', 
        help="Run bos rebalances",
    )
    
    #subparsers = parent_parser.add_subparsers(title="actions")
    #bos_subparsers = subparsers.add_parser(title="Bos rebalance actions")
    #parser_create = subparsers.add_parser("create", parents=[parent_parser],
                                          # add_help=False,
                                          # description="The create parser",
                                          # help="create the orbix environment")
    #parser_create.add_argument("--name", help="name of the environment")
    
    
    # bos_subparsers.add_argument(
        # "-l",
        # "--list",
        # parents=["-b"],
        # action='store_true', 
        # help="Show running bos rebalances",
    # )
    # rebalance_subparsers = subparsers.add_subparsers(title="List past rebalances")
    # rebalance_subparsers.add_parser(
        # "-l",
        # "--list",
        # parents=["-r"],
        # action='store_true', 
        # help="Show list of rebalances",
    # )
    # rebalance_subparsers.add_parser(
        # "-d",
        # "--days",
        # parents=["-r"],
        # type=int,
        # default=7,
        # help="Interval in days (default: 7)",
    # )
    # rebalance_subparsers.add_parser(
        # "-s",
        # "--summary",
        # parents=["-r"],
        # action='store_true', 
        # help="Print summary of rebalances",
    # )
    
    # htlc_subparsers = subparsers.add_subparsers(title="Pending HTLCs actions")
    # htlc_subparsers.add_parser(
        # "-t",
        # "--telegram",
        # action='store_true', 
        # help="Output in Telegram format",
    # )
    
    
    # parent_parser = argparse.ArgumentParser(description="The parent parser")
    # parent_parser.add_argument("-p", type=int, required=True,
                               # help="set db parameter")
    # subparsers = parent_parser.add_subparsers(title="actions")
    # parser_create = subparsers.add_parser("create", parents=[parent_parser],
                                          # add_help=False,
                                          # description="The create parser",
                                          # help="create the orbix environment")
    # parser_create.add_argument("--name", help="name of the environment")
    # parser_update = subparsers.add_parser("update", parents=[parent_parser],
                                          # add_help=False,
                                          # description="The update parser",
                                          # help="update the orbix environment")
    return parent_parser
    
success = main()