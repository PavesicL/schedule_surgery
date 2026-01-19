"""
Contains the construction of the model.
"""
import os
import csv
import math
import pandas as pd
from ortools.sat.python import cp_model

from schedule_surgery.days import Day
from schedule_surgery.worker import Worker
import schedule_surgery.workplaces as wps

def construct_and_optimize(worker_list : list[Worker],
                           day_list : list[Day],
                           preschedule : list[list[str, Day, str]],
                           config : dict) -> pd.DataFrame:
    """
    Defines the model used for optimization, and optimizes it.

    See the Readme for the explanation of the constraints.

    The model is optimized by minimizing the difference between the smallest and
    largest amount of work assigned. This aims to equally distribute the workload.
    An alternative would be to minimize the variance of the distribution of assigned
    work.

    Arguments:
        worker_list : list[Worker]
            List of Worker objects containing their requests.
        day_list : list[Day]
            List of days in the month.
        preschedule : list
            A list of (name, Day, workplace) for prescheduled slots.
        config : dict
            The dictionary of the weights and other input parameters.

    Returns:
        None, the result is saved to schedule.tsv
    """

    # define an empty model
    model = cp_model.CpModel()

    # some useful numbers
    num_workers = len(worker_list)
    num_workplaces = len(wps.ALL_WORKPLACES)

    num_days = len(day_list)
    num_workdays = len([ day for day in day_list if day.is_workday ])
    weekend_pairs = [ (dd, dd+1) for dd, day in enumerate(day_list[:-1]) if day.is_weekend and day_list[dd+1].is_weekend ]


    # Variables: work[(ww, dd, pp)] = 1 if worker w works site s on day d
    # In for loops: ww - workers, dd - days, pp - places
    work = {}
    for ww in range(num_workers):
            for dd in range(num_days):
                for pp in range(num_workplaces):
                    work[ww, dd, pp] = model.NewBoolVar(f'work_{ww}_{dd}_{pp}')


    ### Set the variables from the preschedule:
    worker_names = [worker.name for worker in worker_list]
    preschedule_constraints = []
    for prescheduled_worker_name, day, workplace in preschedule:
        day_ndx = day_list.index(day)
        workplace_ndx = wps.ALL_WORKPLACES.index(workplace)

        if prescheduled_worker_name in worker_names:
            # if the prescheduled person is also in the list of people,
            # give them a work[]==1
            ww_ndx = worker_names.index(prescheduled_worker_name)
            model.Add(work[ww_ndx, day_ndx, workplace_ndx] == 1)

        else:
            # if not in the list, do not allow anyone to work that workplace that day
            for ww in range(num_workers):
                model.Add(work[ww, day_ndx, workplace_ndx] == 0)
            preschedule_constraints.append((day_ndx, workplace_ndx))


    ### unconnected workplaces availability:
    # For the unconnected workplaces we typically have much less workers, so it might happen
    # that no worker is available on some day
    # Find days when noone is available and leave them empty.
    empty_days_abd = []
    empty_days_abd_prip = []
    empty_days_travma_prip = []
    for dd, day in enumerate(day_list):
        avail_workers_abd = []
        avail_workers_abd_prip = []
        avail_workers_travma = []

        if (dd, wps.get_ndx("ABDOMEN")) in preschedule_constraints:
            avail_workers_abd.append("preschedule")
        if (dd, wps.get_ndx("TRAVMA")) in preschedule_constraints:
            empty_days_travma_prip.append("preschedule")
        if (dd, wps.get_ndx("ABD prip.")) in preschedule_constraints:
            avail_workers_abd_prip.append("preschedule")


        for ww, worker in enumerate(worker_list):
            avail_day, avail_night =  worker.workdates[dd]
            if (avail_day in [ +1, 0 ]) and (avail_night in [ +1, 0 ]):

                if worker.works_abd_dez > 0:
                    avail_workers_abd.append(worker.name)

                if worker.works_travma_prip > 0:
                    avail_workers_travma.append(worker.name)

                if day.is_workday:
                    if worker.works_abd_prip > 0:
                        avail_workers_abd_prip.append(worker.name)
                else:
                    # trick because we only care about abd_prip on weekdays
                    avail_workers_abd_prip.append(None)

        if len(avail_workers_abd) == 0:
            empty_days_abd.append(day)
            print(f"\nWARNING: Nobody is available for ABDOMEN on {day}.")
            print("Add a fake entry on this day into the preschedule, and reduce the number of shifts by one.")
            exit()
        if len(avail_workers_abd_prip) == 0:
            empty_days_abd_prip.append(day)
            print(f"\nWARNING: Nobody is available for ABD prip. on {day}.")
            print("Add a fake entry on this day into the preschedule, and reduce the number of shifts by one.")
            exit()
        if len(avail_workers_travma) == 0:
            empty_days_travma_prip.append(day)
            print(f"\nWARNING: Nobody is available for TRAVMA on {day}.")
            print("Add a fake entry on this day into the preschedule, and reduce the number of shifts by one.")
            exit()

    ################################################################################
    # HARD CONSTRAINTS

    # Constraint #######################################################################
    # exactly one worker per site, unless already assigned.
    if 1:
        for dd, day in enumerate(day_list):
            for pp in range(num_workplaces):
                if (dd, pp) not in preschedule_constraints:
                    if (pp == wps.get_ndx("ABD prip.")) and (not day.is_workday):
                        # abd prip is only on workdays
                        total = 0
                    else:
                        total = 1
                else:
                    total = 0

                model.Add(sum(work[ww, dd, pp] for ww in range(num_workers)) == total)

    # Constraint #######################################################################
    # not all workers work all workplaces
    if 1:
        for ww, worker in enumerate(worker_list):
            for dd in range(num_days):
                for pp, workplace in enumerate(wps.ALL_WORKPLACES):
                    if pp in worker.workplaces["NO"]:
                        model.Add( work[ww, dd, pp] == 0 )

    # Constraint #######################################################################
    # The unconnected worksplaces have a pre-defined number of shifts
    if 1:
        # first check whether the sum of these is correct

        sum_abd_dez = sum([worker.works_abd_dez for worker in worker_list])
        sum_abd_prip = sum([worker.works_abd_prip for worker in worker_list])
        sum_travma_prip = sum([worker.works_travma_prip for worker in worker_list])
        if sum_abd_dez != num_days:
            print(f"The total number of abd_dez is {sum_abd_dez}. Should be {num_days}.")
        if sum_abd_prip != num_workdays:
            print(f"The total number of abd_prip is {sum_abd_prip}. Should be {num_workdays}.")
        if sum_abd_dez != num_days:
            print(f"The total number of travma_prip is {sum_travma_prip}. Should be {num_days}.")

        # enforce that each worker is scheduled a preset number of times
        for ww, worker in enumerate(worker_list):
            model.Add( sum(work[ww, dd, wps.get_ndx("ABDOMEN")] for dd in range(num_days)) == worker.works_abd_dez )
            model.Add( sum(work[ww, dd, wps.get_ndx("ABD prip.")] for dd, day in enumerate(day_list) if day.is_workday) == worker.works_abd_prip )
            model.Add( sum(work[ww, dd, wps.get_ndx("TRAVMA")] for dd in range(num_days)) == worker.works_travma_prip )

    # Constraint #######################################################################
    # never from night shift to next day day shift
    if 1:
        for ww, worker in enumerate(worker_list):
            for dd in range(num_days - 1):
                model.Add( sum(work[ww, dd, ppn] for ppn in wps.range_night_workplaces) + sum(work[ww, dd+1, ppd] for ppd in wps.range_day_workplaces) <= 1 )

    # Constraint #######################################################################
    # if workday, never from day shift to night shift
    if 1:
        for ww, worker in enumerate(worker_list):
            for dd, day in enumerate(day_list):
                if day.is_workday:
                    model.Add(sum(work[ww, dd, ppd] for ppd in wps.range_day_workplaces) + sum(work[ww, dd, ppn] for ppn in wps.range_night_workplaces) <= 1 )

    # Constraint #######################################################################
    # do not schedule unconnected workplaces if working something else already

    if 1:
        # Can't work at unconnected workplaces if already working elsewhere
        for ww in range(num_workers):
            for dd in range(num_days):
                # At most 1 workplace total if any is unconnected
                # This ensures: if at unconnected workplace, nowhere else; if elsewhere, not at unconnected

                is_at_unconnected = model.NewBoolVar(f'at_unconnected_{ww}_{dd}')
                model.AddMaxEquality(is_at_unconnected, [work[ww, dd, pp] for pp in wps.range_unconnected_workplaces])

                # If at unconnected, total workplaces must be exactly 1 (the unconnected one)
                model.Add(sum(work[ww, dd, pp] for pp in range(num_workplaces)) == 1).OnlyEnforceIf(is_at_unconnected)

    # Constraint #######################################################################
    # do not work more that two consecutive days
    # First, create "is working" variables for all workers and days
    is_working = {}
    for ww in range(num_workers):
        for dd in range(num_days):
            is_working[ww, dd] = model.NewBoolVar(f'working_{ww}_{dd}')
            model.AddMaxEquality(is_working[ww, dd], [work[ww, dd, pp] for pp in range(num_workplaces)])

    # Then add the consecutive day constraint
    for ww in range(num_workers):
        for dd in range(num_days - 2):
            model.Add(is_working[ww, dd] + is_working[ww, dd+1] + is_working[ww, dd+2] <= 2)


    # Constraint #######################################################################
    # Weekends:
    # if working night shifts, at most one weekend day, where they work one day and one night shift. Exactly one of them is MOP (KRG 3 or KRG N - MOP )
    # if not working night shifts, at most one weekend with two consecutive days working
    if 1:
        for ww, worker in enumerate(worker_list):
            if worker.works_night_shifts:
                mop24_list = [] # counts how many 24h a worker gets per month
                for dd, day in enumerate(day_list):
                    if day.is_weekend or day.is_holiday:

                        ##### one person works MOP day (krg3) and night ABD or B
                        works_24_mop_day = model.NewBoolVar(f'works_24_mop_day_{ww}_{dd}')
                        model.Add(work[ww, dd, wps.mop_day_ndx] == works_24_mop_day)
                        model.Add(work[ww, dd, wps.abd_night_ndx] + work[ww, dd, wps.b_night_ndx] == 1).OnlyEnforceIf(works_24_mop_day)

                        # it not working MOP, work at most one of the night shifts (but not MOP-N)
                        model.Add(work[ww, dd, wps.abd_night_ndx] + work[ww, dd, wps.b_night_ndx] <= 1).OnlyEnforceIf(works_24_mop_day.Not())
                        mop24_list.append(works_24_mop_day)
                        #####

                        ##### one person works MOP-N and day ABD or B (krg1, krg2)
                        works_24_mop_night = model.NewBoolVar(f'works_24_mop_night_{ww}_{dd}')
                        model.Add(work[ww, dd, wps.mop_night_ndx] == works_24_mop_night)
                        model.Add(work[ww, dd, wps.abd_day_ndx] + work[ww, dd, wps.b_day_ndx] == 1).OnlyEnforceIf(works_24_mop_night)

                        # if not working MOP-N, work at most one of the day shifts
                        model.Add(work[ww, dd, wps.abd_day_ndx] + work[ww, dd, wps.b_day_ndx] <= 1).OnlyEnforceIf(works_24_mop_night.Not())
                        mop24_list.append(works_24_mop_night)
                        #####

                        # This is equivalent to Bool OR
                        works_24_day = model.NewBoolVar(f'works_24_mop_day_{ww}_{dd}')
                        model.AddMaxEquality(works_24_day, [works_24_mop_day, works_24_mop_night])

                        # if a person works this, do not schedule them one day before or after
                        if dd < num_days-1:
                            model.Add(sum(work[ww, dd+1, pp] for pp in range(num_workplaces)) == 0).OnlyEnforceIf(works_24_day)
                        if dd > 0:
                            model.Add(sum(work[ww, dd-1, pp] for pp in range(num_workplaces)) == 0).OnlyEnforceIf(works_24_day)

                # at most one 24h per month
                model.Add(sum(mop24_list) <= 1)
            else:
                # figure out weekends:
                works_weekend_pair_list = []
                for pair_idx, (dd1, dd2) in enumerate(weekend_pairs):
                    works_pair = model.NewBoolVar(f'works_weekend_pair_{ww}_{pair_idx}')

                    shifts_dd1 = sum(work[ww, dd1, pp] for pp in wps.range_day_workplaces)
                    shifts_dd2 = sum(work[ww, dd2, pp] for pp in wps.range_day_workplaces)

                    # works_pair is True if worker has shifts on BOTH days
                    works_dd1 = model.NewBoolVar(f'works_{ww}_dd1_{pair_idx}')
                    works_dd2 = model.NewBoolVar(f'works_{ww}_dd2_{pair_idx}')

                    model.Add(shifts_dd1 >= 1).OnlyEnforceIf(works_dd1)
                    model.Add(shifts_dd1 == 0).OnlyEnforceIf(works_dd1.Not())

                    model.Add(shifts_dd2 >= 1).OnlyEnforceIf(works_dd2)
                    model.Add(shifts_dd2 == 0).OnlyEnforceIf(works_dd2.Not())

                    # works_pair = True only if BOTH days are worked
                    model.AddBoolAnd([works_dd1, works_dd2]).OnlyEnforceIf(works_pair)
                    model.AddBoolOr([works_dd1.Not(), works_dd2.Not()]).OnlyEnforceIf(works_pair.Not())

                    works_weekend_pair_list.append(works_pair)

                # at most one weekend pair worked per month for this worker
                model.Add(sum(works_weekend_pair_list) <= 1)

    # Constraint #######################################################################
    # At most one shift per day/night, if they can work on that day

    if 1:
        for ww, worker in enumerate(worker_list):
            for dd in range(num_days):
                # these will be +1 or 0 if they can work, and -1 if they cant
                # The +1 is treated in a soft constraint below
                avail_day, avail_night = worker.workdates[dd]

                # day shifts
                if avail_day in [ +1, 0 ]:
                    model.Add( sum( work[ww, dd, pp] for pp in wps.range_day_workplaces) <= 1)
                else:
                    model.Add( sum( work[ww, dd, pp] for pp in wps.range_day_workplaces) == 0)

                # night shifts
                if avail_night in [ +1, 0 ]:
                    model.Add( sum( work[ww, dd, pp] for pp in wps.range_night_workplaces) <= 1)
                else:
                    model.Add( sum( work[ww, dd, pp] for pp in wps.range_night_workplaces) == 0)

                # 24h unconnected workplaces
                if (avail_day in [ +1, 0 ]) and (avail_night in [ +1, 0 ]):
                    model.Add( sum( work[ww, dd, pp] for pp in wps.range_unconnected_workplaces) <= 1)
                else:
                    model.Add( sum( work[ww, dd, pp] for pp in wps.range_unconnected_workplaces) == 0)

    # Constraint #######################################################################
    # Some workers have a limited number of day shifts
    if 1:
        for ww, worker in enumerate(worker_list):
            if not math.isnan(worker.max_num_dayshifts):
                model.Add( sum( work[ww, dd, pp] for dd in range(num_days) for pp in wps.range_day_workplaces ) <= worker.max_num_dayshifts)

    # Constraint #######################################################################
    # The number of night shifts is limited from below with the number that depends on the workers status,
    # and from above with 5 - worker.reduce_shifts.
    if 1:
        total_min_shifts = 0
        total_max_shifts = 0

        # first count the possible minimal and maximal number of night shifts
        for ww, worker in enumerate(worker_list):
            if worker.works_night_shifts:
                min_shifts = worker.min_night_shifts
                max_shifts = max(min_shifts, 5 - worker.reduce_shifts)

                total_min_shifts += min_shifts
                total_max_shifts += max_shifts

        total_night_places = len(list(wps.range_night_workplaces)) * num_days
        #print(f"Counting possible night shifts: {total_min_shifts=}, {total_max_shifts=}, {total_night_places=}")

        # if total_max_shifts is smaller than total_night_places, or total_min_shifts smaller than total_night_places we have a problem!
        if total_max_shifts < total_night_places:
            print(f"Problem: {total_max_shifts=} < {total_night_places=}! The total maximal possible number of night shifts is smaller than the number of night shifts in the month.")
        if total_min_shifts > total_night_places:
            print(f"Problem: {total_min_shifts=} > {total_night_places=}! The total minimum required number of night shifts is bigger than the number of night shifts in the month.")

        # TODO how to solve this problem if it appears?

        for ww, worker in enumerate(worker_list):
            if worker.works_night_shifts:
                min_shifts = worker.min_night_shifts
                max_shifts = max(min_shifts, 5 - worker.reduce_shifts)

                total_min_shifts += min_shifts
                total_max_shifts += max_shifts

                if max_shifts < min_shifts:
                    model.Add( sum(work[ww, dd, pp] for pp in wps.range_night_workplaces for dd in range(num_days)) == 0 )
                else:
                    model.Add( sum(work[ww, dd, pp] for pp in wps.range_night_workplaces for dd in range(num_days)) >= min_shifts )
                    model.Add( sum(work[ww, dd, pp] for pp in wps.range_night_workplaces for dd in range(num_days)) <= max_shifts )

    # Constraint #######################################################################
    # worker.specialty == "KROŽEČI" are special.
    # They should be scheduled a certain number of times. This is given in the config file, in weights.
    if 1:
        for ww, worker in enumerate(worker_list):
            if worker.specialty[1] == "Krožeči":
                # check that the worker actually can work these many days
                eligible_days = 0
                for dd in range(num_days):
                    if worker.workdates[dd][0] in [0, +1]:
                        eligible_days += 1
                if eligible_days < config["krozeci_scheduled"]:
                    raise Exception(f"{worker.name} is Krožeči and should be scheduled {config['krozeci_scheduled']}x, but can only work {eligible_days} days.")

                model.Add( sum(work[ww, dd, pp] for dd in range(num_days) for pp in range(num_workplaces)) == config["krozeci_scheduled"])

    # Constraint #######################################################################
    # worker.included == "OMEJENO" are special. They are scheduled a pre-set number of times.
    if 1:
        for ww, worker in enumerate(worker_list):
            if worker.included == "OMEJENO":
                if math.isnan(worker.num_dayshifts_omejeno):
                    raise Exception(f"For {worker.name} found {worker.num_dayshifts_omejeno=}. Should be integer.")
                if math.isnan(worker.num_nightshifts_omejeno):
                    raise Exception(f"For {worker.name} found {worker.num_nightshifts_omejeno=}. Should be integer.")

                model.Add( sum( work[ww, dd, pp] for dd in range(num_days) for pp in wps.range_day_workplaces ) == worker.num_dayshifts_omejeno )
                model.Add( sum( work[ww, dd, pp] for dd in range(num_days) for pp in wps.range_night_workplaces ) == worker.num_nightshifts_omejeno )


    ########################################################################
    # SOFT CONSTRAINTS ####################################################
    ########################################################################
    # All input weights should be positive integers.
    # The objective is minimized; things will happen if their weight is small.

    # Penalty #######################################################################
    # schedule workers when they want to work

    # the trick is to define a new variable, and assign it to some number:
    # here, the number of times we assigned a worker to a preferential date.
    # The night and day shift are treated separately because sometimes people can
    # only work either day or night, but summed.

    penalty_preferential_assignment_day = model.NewIntVar(0, num_workers * num_days * num_workplaces, "penalty_preferential_assignment_day")
    model.Add(penalty_preferential_assignment_day ==
                sum(
                    work[ww, dd, pp] for pp in wps.range_day_workplaces
                            for dd in range(num_days)
                            for ww, worker in enumerate(worker_list) if worker.workdates[dd][0] == +1
                            ) +
                sum(
                    work[ww, dd, pp] for pp in wps.range_night_workplaces
                            for dd in range(num_days)
                            for ww, worker in enumerate(worker_list) if worker.workdates[dd][1] == +1
                            )
        )

    # also prefer working unconnected, but only if both worker.workdates entries are +1 (they are available 24h)
    penalty_preferential_assignment_day_unconnected = model.NewIntVar(0, num_workers * num_days, "penalty_preferential_assignment_day_unconnected")
    model.Add(penalty_preferential_assignment_day_unconnected == sum(work[ww, dd, pp] for pp in wps.range_unconnected_workplaces for dd in range(num_days) for ww, worker in enumerate(worker_list) if worker.workdates[dd] == (+1, +1))
    )

    # Penalty #######################################################################
    # Preferrentially work workplaces which are YES (instead of MAYBE)
    penalty_preferential_workplace = model.NewIntVar(-num_workers * num_days * num_workplaces, num_workers * num_days * num_workplaces, "penalty_preferential_assignment_day")
    model.Add(penalty_preferential_workplace ==
              sum(work[ww, dd, pp] for ww, worker in enumerate(worker_list) for dd in range(num_days) for pp in worker.workplaces["MAYBE"] ) -
              sum(work[ww, dd, pp] for ww, worker in enumerate(worker_list) for dd in range(num_days) for pp in worker.workplaces["YES"] )
              )

    # Penalty #######################################################################
    # On a weekend, preferrentially work two consecutive travma-prip
    # prefer this for older workers

    # we already have weekend pairs
    bonus_weekend_travmaprip = model.NewIntVar(0, len(weekend_pairs), "bonus_weekend_travmaprip")
    ndx_travma_prip = wps.get_ndx("TRAVMA")

    # Calculate seniority tiers; preferrably assign this to older workers
    years = [worker.year_of_specialization for worker in worker_list]
    max_year = max(years)

    consecutive_weekends = []
    for dd1, dd2 in weekend_pairs:

        # Count workers assigned to BOTH days
        for ww in range(num_workers):
            # This worker gets both days
            both = model.NewBoolVar(f'both_weekend_days_{ww}_{dd1}_{dd2}')
            model.Add(work[ww, dd1, ndx_travma_prip] + work[ww, dd2, ndx_travma_prip] == 2).OnlyEnforceIf(both)
            model.Add(work[ww, dd1, ndx_travma_prip] + work[ww, dd2, ndx_travma_prip] != 2).OnlyEnforceIf(both.Not())
            consecutive_weekends.append(both)

    model.Add(bonus_weekend_travmaprip == sum(consecutive_weekends))

    #######################################################################
    # Bonus for assigning consecutive weekends to older workers (exponential preference)
    bonus_weekend_travmaprip_senior = model.NewIntVar(
        0,
        len(weekend_pairs) * num_workers * (2 ** 7),  # Adjust upper bound based on max seniority
        "bonus_weekend_travmaprip_senior"
    )

    ndx_travma_prip = wps.get_ndx("TRAVMA")
    consecutive_weekends = []
    consecutive_weekends_weighted = []

    # Get max year for seniority calculation
    max_year = max(w.year_of_specialization for w in worker_list)

    for dd1, dd2 in weekend_pairs:
        for ww, worker in enumerate(worker_list):
            # This worker gets both days
            both = model.NewBoolVar(f'both_weekend_days_{ww}_{dd1}_{dd2}')
            model.Add(work[ww, dd1, ndx_travma_prip] + work[ww, dd2, ndx_travma_prip] == 2).OnlyEnforceIf(both)
            model.Add(work[ww, dd1, ndx_travma_prip] + work[ww, dd2, ndx_travma_prip] != 2).OnlyEnforceIf(both.Not())
            consecutive_weekends.append(both)

            # Exponential weight: doubles for each year of seniority
            years_of_seniority = max_year - worker.year_of_specialization
            weight = 2 ** (7 - years_of_seniority)

            consecutive_weekends_weighted.append(both * weight)

    # Total count (unweighted) - if you still need it
    bonus_weekend_travmaprip = model.NewIntVar(0, len(weekend_pairs) * num_workers, "bonus_weekend_travmaprip")
    model.Add(bonus_weekend_travmaprip == sum(consecutive_weekends))

    # Weighted sum favoring senior workers
    model.Add(bonus_weekend_travmaprip_senior == sum(consecutive_weekends_weighted))

    # Add to your objective function
    # model.Maximize(... + bonus_weekend_travmaprip_senior * coefficient + ...)

    # Penalty #######################################################################
    # TODO equally distribute each worker's shits across the month
    # ???



    # Penalty #######################################################################
    # penalize two consecutive night shifts
    penalty_consecutive_nights = []
    for ww in range(num_workers):
        for dd in range(num_days-1):

            # Add auxiliary variables
            consecutive_night = model.NewBoolVar(f'consecutive_night_{ww}_{dd}')
            night_today = model.NewBoolVar(f'night_{ww}_{dd}')
            night_tomorrow = model.NewBoolVar(f'night_{ww}_{dd+1}')

            # Link to actual night workplace assignments
            model.Add(sum(work[ww, dd, pp] for pp in wps.range_night_workplaces) >= 1).OnlyEnforceIf(night_today)
            model.Add(sum(work[ww, dd, pp] for pp in wps.range_night_workplaces) == 0).OnlyEnforceIf(night_today.Not())

            model.Add(sum(work[ww, dd+1, pp] for pp in wps.range_night_workplaces) >= 1).OnlyEnforceIf(night_tomorrow)
            model.Add(sum(work[ww, dd+1, pp] for pp in wps.range_night_workplaces) == 0).OnlyEnforceIf(night_tomorrow.Not())

            # consec_night is true only if both nights are worked
            model.AddBoolAnd([night_today, night_tomorrow]).OnlyEnforceIf(consecutive_night)
            model.AddBoolOr([night_today.Not(), night_tomorrow.Not()]).OnlyEnforceIf(consecutive_night.Not())

            penalty_consecutive_nights.append(consecutive_night)
    # in the cost function: sum(penalty_consecutive_nights)

    # Penalty #######################################################################
    # equally distribute each worker among their YES workplaces

    penalty_workplace_distribution = []
    for ww, worker in enumerate(worker_list):
        available_workplaces = worker.workplaces["YES"]

        tmp = []
        for awp in available_workplaces:
            if awp not in wps.range_unconnected_workplaces:
                tmp.append(awp)
        available_workplaces = tmp

        if len(available_workplaces) <= 1:
            continue

        # Count total shifts for this worker at each workplace
        workplace_counts = {}
        for pp in available_workplaces:
            workplace_counts[pp] = sum(work[ww, dd, pp] for dd in range(num_days))

        # Minimize the difference between max and min workplace counts
        max_count = model.NewIntVar(0, num_days, f'max_workplace_{ww}')
        min_count = model.NewIntVar(0, num_days, f'min_workplace_{ww}')

        # Ensure max_count EQUALS the maximum value
        model.AddMaxEquality(max_count, [workplace_counts[pp] for pp in available_workplaces])
        # Ensure min_count EQUALS the minimum value
        model.AddMinEquality(min_count, [workplace_counts[pp] for pp in available_workplaces])

        # Penalize the range (max - min)
        range_var = model.NewIntVar(0, num_days, f'range_{ww}')
        model.Add(range_var == max_count - min_count)

        penalty_workplace_distribution.append(range_var)


    ########################################################################
    ########################################################################
    # Objective: overall equal workload
    # We minimize the difference between the largest and the smallest amount of work assigned.
    # Not all workplaces are weighed equally.

    workplace_weights = config["workplace_weights"]

    max_possible_work = num_days * max(workplace_weights.values()) # one shift per day is the max
    total_workloads = []
    worker_list_for_workload = []
    for ww, worker in enumerate(worker_list):

        if worker.specialty_wishes in [ "Krožeči", ] or worker.specialty_master in [ "Krožeči", ]:
            # these guys are assigned an exact number of times
            continue

        # the weights depend on the workers age, and whether it is a workday or not
        weight_night = workplace_weights[f"night_{worker.year_of_specialization}"]
        weight_workday = workplace_weights["workday"]
        weight_weekend = workplace_weights["weekend"]
        wp_weight = lambda day, workplace_ndx : weight_night if workplace_ndx in list(wps.range_night_workplaces) else weight_workday if day.is_workday else weight_weekend

        total = model.NewIntVar(0, max_possible_work, f'total_workload_{ww}')
        model.Add(total == sum( wp_weight(day, pp) * work[ww, dd, pp] for dd, day in enumerate(day_list) for pp in list(wps.range_day_workplaces) + list(wps.range_night_workplaces) ) )
        total_workloads.append(total)
        worker_list_for_workload.append(worker) # we are ignoring "KROZECI" se we need a new list

    max_workload = model.NewIntVar(0, max_possible_work, 'max_workload')
    min_workload = model.NewIntVar(0, max_possible_work, 'min_workload')
    model.AddMaxEquality(max_workload, total_workloads)
    model.AddMinEquality(min_workload, total_workloads)

    # Objective function:
    model.Minimize(
        config["weight_equal_workload"] * (max_workload - min_workload) +
        config["weight_consecutive_nights"] * sum(penalty_consecutive_nights) +
        config["weight_equally_distributed_workplaces"] * sum(penalty_workplace_distribution) +
        config["weight_preferred_day_assignment"] * (penalty_preferential_assignment_day + penalty_preferential_assignment_day_unconnected) +
        config["weight_preferred_workplace_assignment"] * penalty_preferential_workplace +
        -1 * config["weight_weekend_travmaprip"] * bonus_weekend_travmaprip_senior
        )

    # Solve model
    solver = cp_model.CpSolver()

    print("Solving the model...")
    # Enable logging to see progress

    if config["print_logs"]:
        solver.parameters.log_search_progress = True
        # Optional: Control how often logs appear (in seconds)
        solver.parameters.log_to_stdout = 5
    solver.parameters.num_search_workers = os.cpu_count()
    solver.parameters.max_time_in_seconds = config["time_limit"]

    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    print()
    print(f"Finished, the optimizer status is {status_name}.")

    if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        raise Exception(f"The optimization was not successful. The solver status is {status_name}.")


    # Generate an empty schedule array.
    ncols = len(wps.ALL_WORKPLACES) + 2
    nrows = num_days + 1
    schedule_array = [ [ "" for _ in range(ncols) ] for _ in range(nrows)]

    # add workplaces as the header
    workplaces_header = ["DATUM", ] + wps.ALL_WORKPLACES
    schedule_array[0] = workplaces_header

    # add dates in the first column
    for ii in range(1, len(schedule_array)):
        schedule_array[ii][0] = str(day_list[ii-1])

    # fill in the preschedule
    for (name, day, workplace) in preschedule:
        day_index = day_list.index(day)
        workplace_index = wps.ALL_WORKPLACES.index(workplace)
        schedule_array[day_index+1][workplace_index+1] = name

    # fill in the schedule
    for dd, day in enumerate(day_list):
        for ww, worker in enumerate(worker_list):
            for pp, workplace in enumerate(wps.ALL_WORKPLACES):
                if solver.Value(work[ww, dd, pp]) == 1:
                    schedule_array[dd+1][pp+1] = worker.name

    ########################################################################
    # Collect and print some stats.

    number_of_shifts = [ (worker, sum( solver.Value(work[ww, dd, pp]) for dd in range(num_days) for pp in range(num_workplaces))) for ww, worker in enumerate(worker_list)]
    number_of_shifts = sorted(number_of_shifts, key=lambda x : -x[1])

    all_workloads = [ (worker_list_for_workload[ii].name, solver.Value(total_workloads[ii])) for ii in range(len(worker_list_for_workload)) ]
    all_workloads = sorted(all_workloads, key=lambda x : -x[1])

    # how many times each person works each workplace
    shifts_count_array = []
    for ww, worker in enumerate(worker_list):
        shifts_count_ww = [ worker.name, ]
        shifts_count_ww += [ sum(solver.Value(work[ww,dd,pp]) for dd in range(num_days)) for pp in range(num_workplaces) ]
        shifts_count_array.append(shifts_count_ww)
    shifts_count_array = [ x for _, x in sorted(zip(worker_list, shifts_count_array), key=lambda x: x[0].specialty_master) ]
    shifts_count_array.insert(0, workplaces_header)

    if 0:
        print("NUMBER OF SHIFTS:")
        for name, num_shifts in number_of_shifts:
            print(name, num_shifts)

        print("WORKLOADS:")
        for name, load in all_workloads:
            print(name, load)

    print(f"The worker with the largest number of shifts is {number_of_shifts[0][0]} with {number_of_shifts[0][1]}.")
    print(f"The worker with the smallest number of shifts is {number_of_shifts[-1][0]} with {number_of_shifts[-1][1]}.")
    print()
    print(f"The worker with the largest workload is {all_workloads[0][0]} with {all_workloads[0][1]}.")
    print(f"The worker with the smallest workload is {all_workloads[-1][0]} with {all_workloads[-1][1]}.")
    print("###########################")

    ########################################################################
    # Write the output as a csv file.

    print(f"Writing output to schedule.csv...")
    with open('schedule.csv', 'w') as myfile:
        wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
        for row in schedule_array:
            wr.writerow(row)

    # and write the stats

    print(f"Writing stats to stats.csv...")
    with open('stats.csv', 'w') as myfile:
        wr = csv.writer(myfile, quoting=csv.QUOTE_ALL)
        for row in shifts_count_array:
            wr.writerow(row)

    ########################################################################
    df_schedule = pd.DataFrame(schedule_array)
    df_stats = pd.DataFrame(shifts_count_array)
    return df_schedule, df_stats
