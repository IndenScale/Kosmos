# cli/commands/logs.py
import argparse
import subprocess
import os
import sys
from typing import List

from ..config import CliConfig
from ..knowledge_base_client import KosmosClient

def register_subparser(subparsers: argparse._SubParsersAction, parent_parser: argparse.ArgumentParser):
    """
    Registers the 'logs' command and its arguments, following the project's established pattern.
    """
    parser = subparsers.add_parser(
        "logs",
        parents=[parent_parser],
        help="Show the tail of all service log files for a quick status overview.",
    )
    parser.add_argument(
        "-n",
        "--lines",
        type=int,
        default=15,
        help="Number of lines to show from the end of each log file.",
    )
    parser.set_defaults(func=run)

def run(client: KosmosClient, args: argparse.Namespace, config: CliConfig):
    """
    Executes the 'logs' command.
    """
    # --- 1. Check Message Queues --- 
    print("--- [CLI] Checking message queue status ---")
    try:
        # We execute the existing check_queues.py script. This promotes code reuse.
        check_queues_path = os.path.join(os.path.dirname(__file__), '..', '..', 'check_queues.py')
        
        # Ensure the script is executable by the python in the venv
        python_executable = os.path.join(os.path.dirname(sys.executable), 'python')

        queue_result = subprocess.run(
            [python_executable, check_queues_path],
            capture_output=True,
            text=True,
            check=False,
            encoding='utf-8'
        )
        
        if queue_result.returncode == 0:
            # Print the relevant output from the script
            print(queue_result.stdout)
        else:
            print("\n--- [WARNING] Could not fetch queue status. ---")
            if queue_result.stderr:
                print("  - Error Details:")
                print(queue_result.stderr)

    except FileNotFoundError:
        print("\n--- [ERROR] The 'check_queues.py' script or python executable was not found. ---")
    except Exception as e:
        print(f"\n--- [ERROR] An unexpected error occurred while checking queues: {e} ---")

    # --- 2. Fetch Logs --- 
    print(f"\n--- [CLI] Fetching the last {args.lines} lines of all logs in the 'logs/' directory ---")
    
    try:
        command = f"tail -n {args.lines} logs/*"
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("\n--- [WARNING] Could not fetch logs. ---")
            if result.stderr:
                print("  - Error Details:")
                print(result.stderr)
            else:
                print("  - The 'logs/' directory may not exist or might be empty.")

    except FileNotFoundError:
        print("\n--- [ERROR] The 'tail' command was not found on your system. ---")
    except Exception as e:
        print(f"\n--- [ERROR] An unexpected error occurred while fetching logs: {e} ---")

