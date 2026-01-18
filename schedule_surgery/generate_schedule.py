#!/usr/bin/env python

"""
Generates a schedule for a given month.
"""

import argparse
import random
import json

from datetime import date

from schedule_surgery import days
from schedule_surgery import parsing
from schedule_surgery import optimize

def main():
    # Parse the command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('zelje')
    parser.add_argument('mastersheet')
    parser.add_argument('preschedule')
    parser.add_argument('config')
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)


    # parse the dates
    start_date = date.fromisoformat(config["start_date"])
    end_date = date.fromisoformat(config["end_date"])
    day_list = days.generate_day_list(start_date=start_date, end_date=end_date)

    worker_list = parsing.parse_workers(args.zelje, args.mastersheet)
    preschedule = parsing.parse_preschedule(args.preschedule)


    print(f"Generating the schedule from {day_list[0]} to {day_list[-1]}.")

    print("The workers are:")
    print([ww.name for ww in worker_list])


    # Because the optimization is so under-determined, the initial conditions make a big difference.
    # These are basically determined by the order in which you loop over the workers.
    # Shuffling the list lets you generate multiple different optimal schedules.
    random.shuffle(worker_list)

    # Construct the model and optimize
    optimize.construct_and_optimize(worker_list=worker_list,
                                    day_list=day_list,
                                    preschedule=preschedule,
                                    config=config)


    print("DONE")




if __name__ == "__main__":
    main()