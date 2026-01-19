"""
The parsing functions to collect the date from the excell file.
The file should be a tab-separated format (.tsv).

We assume the following format:

"""
import math
import datetime
import pandas as pd

import  schedule_surgery.workplaces as wps
from schedule_surgery.worker import Worker
from schedule_surgery.days import Day

def parse_preschedule(filename : str) -> list[list[str, Day, str]]:
    """
    Parses the input preschedule to figure out which date/workplace
    combinations are occupied.
    This should be a three-column .tsv file,
    with columns "ime", "datum", "delovisce".

    Arguments
        filename : str
            The path to the file.
    Return
        list[list[str, Day, str]]
        A list of (name, Day, workplace) which are already assigned.
    """
    df = pd.read_csv(filename, sep="\t")

    date_format = "%d.%m.%Y"

    result = []
    for _, row in df.iterrows():

        date_str = row["Datum"]
        date = datetime.datetime.strptime(date_str, date_format)
        day = Day(date.year, date.month, date.day)

        result.append([
            row["Priimek Ime"].upper(),
            day,
            row["Delovišče"],
        ])

    return result

def parse_workers(filename_wishes : str, filename_mastersheet : str) -> list[Worker]:
    """
    Parses the input from the two files, combines it and generates a list of Worker objects.

    The input comes in two files; a monthly list of wishes and requests
    for each worker, and a more-or-less constant master sheet, which
    contains some additional information about the workers, like which
    workplaces they work at etc.

    Arguments
        filename_wishes : str
            The path to the file with the wishes.
        filename_mastersheet : str
            The path to the mastersheet.
    Return
        list[Worker]
        A list of worker objects.
    """

    dfw = pd.read_csv(filename_wishes, sep="\t")
    dfm = pd.read_csv(filename_mastersheet, sep="\t")

    # remove "Specializant URG" from dfm
    dfm = dfm[ dfm["Specializacija"] != "Specializant URG" ]
    # remove

    # Merge them on the name column. Keeps both sets.

    # these are the strings for the name column
    name_wishes = "Priimek Ime (s šumniki,  v tem zaporedju, v taki obliki, brez presledkov; primer: Novak Janez)"
    name_master = "Priimek Ime"

    # remove whitespace and make uppercase
    dfw[name_wishes] = dfw[name_wishes].str.strip().str.upper()
    dfm[name_master] = dfm[name_master].str.strip().str.upper()

    df = pd.merge(dfw, dfm, left_on=name_wishes, right_on=name_master, how="outer")

    # remove whitespace in names of columns
    df.columns = df.columns.str.strip()

    ################
    # Warnings:

    ### IN wishes, NOT IN mastersheet
    # It can happen that a worker is in the wishes but not in the master sheet.
    # This has to throw an error.
    # We filter for Nans in the column 'VKLJUČEN', because it is only in the master file
    masked_df = df["VKLJUČEN"].isna()
    count = masked_df.sum()
    names = df.loc[masked_df, name_wishes]

    if not names.empty:
        print(f"Found {count} people in the wishes that do not exists in the master sheet. Add them and restart.")
        print("The names are:")
        for name in names:
            print(name)
        exit()

    ### IN mastersheet with NE, IN wishes
    masked_df = df[
        (df["VKLJUČEN"] == "NE") &
        (df["Matična ustanova"].notna())
    ]
    names = masked_df[name_wishes]
    count = len(names)
    if not names.empty:
        print(f"Found {count} people in the master sheet with NE, but with submitted wishes. Fix and restart.")
        print("The names are:")
        for name in names:
            print(name)
        exit()


    ### IN mastersheet, NOT IN wishes
    # This can be because:
    # 1) They are not working that month. We exclude them from the list.
    df = df[ df["VKLJUČEN"] != "NE" ]

    # 2) They have no requests and can work any time. We keep them and enter default values.
    # count them (Maticna ustanova) only appears in the wishes -- this checks that they are not in the wishes.
    mask = df["Matična ustanova"].isna()
    count = mask.sum()
    names = df.loc[mask, name_master]

    if not names.empty:
        print(f"Found {count} people that are not in the wishes, but are in the master sheet with YES/OMEJENO. Assuming they work with no preferences.")
        print("The names are:")
        for name in names:
            print(name)
        print()

    # also, give them names (name_wishes is nan because they are not there)
    df.loc[mask, name_wishes] = df.loc[mask, name_master]

    # they also do not get the status from the wishes. Take it from the master sheet.
    mask = df["Status"].isna()
    df.loc[mask, "Status"] = df.loc[mask, "Letnik specializacije"]

    # The dataset is clean, parse into the workers
    # The only assumption is that the availability columns are
    # between (including) indices 12 and -(len(wishes)-6)
    worker_list = []
    for ii, row in df.iterrows():
        name = row[name_wishes]
        included = row["VKLJUČEN"]

        specialty_wishes = row["Specializacija_x"]
        specialty_master = row["Specializacija_y"]
        status = row["Status"]

        # other workplaces
        # these are integers or nan
        works_abd_dez = int(transform_nan(row["ABD DEŽ"], 0))
        works_abd_prip = int(transform_nan(row["ABD PRIP N"], 0))
        works_travma_prip = int(transform_nan(row["TRA PRIP Št"], 0))

        # limits on num of shifst
        max_num_dayshifts = to_int_or_nan(row["MAX ŠT. DNEVNIH"])
        num_dayshifts_omejeno = to_int_or_nan(row["Št. dnevnih za OMEJENO"])
        num_nightshifts_omejeno = to_int_or_nan(row["Št. nočnih za OMEJENO"])

        workplaces = parse_workplaces(row)
        workdates = parse_work_dates(row, df.columns)
        reduce_shifts = parse_reduce_shifts(row)

        worker = Worker(name=name,
                        included=included,
                        specialty=(specialty_wishes, specialty_master),
                        status=status,
                        workplaces=workplaces,
                        workdates=workdates,
                        reduce_shifts=reduce_shifts,

                        works_abd_dez=works_abd_dez,
                        works_abd_prip=works_abd_prip,
                        works_travma_prip=works_travma_prip,

                        max_num_dayshifts=max_num_dayshifts,
                        num_dayshifts_omejeno=num_dayshifts_omejeno,
                        num_nightshifts_omejeno=num_nightshifts_omejeno
                        )

        worker_list.append(worker)

    return worker_list

def parse_workplaces(row : pd.DataFrame) -> dict:
    """
    Parses which workplaces the worker can definitely work at,
    and at which maybe, or cannot.

    Arguments
        row : pandas DataFrame
            One row of a DataFrame, from which we extract the entries.

    Return
        dict
        Dictionary with keys: YES, MAYBE, NO,
        and values that are indices for the workplaces.
    """
    wp_dict = {
        "YES"   : [],
        "MAYBE" : [],
        "NO"    : []
        }

    for ii, workplace in enumerate(wps.STANDARD_WORKPLACES):
        wp_data = row[workplace]

        # nans a transformed to "NO"
        wp_data = transform_nan(wp_data, "NO")
        wp_dict[wp_data].append(ii)
    return wp_dict



def parse_work_dates(entries : list[str], columns : list[str]):
    """
    Parses which work dates the worker would like to work,
    can not work, and does not care about.
    Arguments
        entries : list[str]
            A list of strings, extracted from the dataframe.

    Return
        list[list[int]]
        A list of pairs for each day; first entry for day shift, second for night.
        +1 means can work, 0 means does not care, -1 means cannot work.
    """
    # Find the first and last column starting with "Razpolozljivost...". These are to column start and end indices.
    first_idx = next(i for i, s in enumerate(columns) if s.startswith("Razpolo"))
    last_idx = max(i for i, s in enumerate(columns) if s.startswith("Razpolo"))

    result = []
    for entry in entries[first_idx : last_idx+1]:

        # nans a transformed to "Mi je vseeno"
        entry = transform_nan(entry, "Mi je vseeno")

        entry = entry.lower()

        if entry in ["da (želim delati)", ]:
            res = [1, 1]
        elif entry in [ "ld (letni dopust)", "dežurstvo, matični dan" ]:
            res = [-1, -1]
        elif entry in [ "mi je vseeno", ]:
            res = [0, 0]
        elif entry in [ "samo podnevi (do 24.00)", ]:
            res = [0, -1]
        elif entry in [ "samo ponoči (po 19.00)", ]:
            res = [-1, 0]
        else:
            raise Exception(f"Unrecognized {entry=} while parsing workdates!")

        result.append(res)
    return result

def parse_reduce_shifts(row):
    if math.isnan(row["ŠTEVILO DEŽURSTEV (OPROŠČENO ŠTEVILO)"]):
        reduce_shifts = 0
    else:
        reduce_shifts = int(row["ŠTEVILO DEŽURSTEV (OPROŠČENO ŠTEVILO)"])
    return reduce_shifts


def transform_nan(entry, transform_to):
    """
    Check whether an entry is a python nan, and transform to
    another value.
    """
    if isinstance(entry, float):
        if math.isnan(entry):
            entry = transform_to
    return entry


def to_int_or_nan(entry):
    """
    Keeps if nan, otherwise transforms to int.
    """
    if math.isnan(entry):
        return entry
    else:
        return int(entry)