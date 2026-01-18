"""
Contains the Worker class.
"""

import schedule_surgery.workplaces as wps

class Worker:
    """
    A worker is an object containing the information
    about each person: their name, work date preferences,
    etc.
    """

    def __init__(self,
                 name,
                 included,
                 specialty,
                 status,
                 workplaces,
                 workdates,
                 reduce_shifts,

                 works_abd_dez,
                 works_abd_prip,
                 works_travma_prip,

                max_num_dayshifts,
                num_dayshifts_omejeno,
                num_nightshifts_omejeno
                 ):

        self.name = name
        self.included = included # can be YES, OMEJEN

        self.specialty = specialty
        self.specialty_wishes = specialty[0]
        self.specialty_master = specialty[1]

        self.works_abd_dez = works_abd_dez
        self.works_abd_prip = works_abd_prip
        self.works_travma_prip = works_travma_prip

        self.status = status
        self.workplaces = self._resolve_workplaces(workplaces)
        self.workdates = workdates
        self.reduce_shifts = reduce_shifts

        self.max_num_dayshifts = max_num_dayshifts
        self.num_dayshifts_omejeno = num_dayshifts_omejeno
        self.num_nightshifts_omejeno = num_nightshifts_omejeno


    def _resolve_workplaces(self, workplaces):
        """
        Add the unconnected workplaces to the workplaces dictionary.
        """
        if self.works_abd_dez == 0:
            workplaces["NO"].append(wps.get_ndx("ABDOMEN"))
        if self.works_abd_prip == 0:
            workplaces["NO"].append(wps.get_ndx("ABD prip."))
        if self.works_travma_prip == 0:
            workplaces["NO"].append(wps.get_ndx("TRAVMA"))
        return workplaces

    @property
    def works_night_shifts(self):
        """
        Whether the worker works night shifts.
        """
        working_workplaces = self.workplaces["YES"] + self.workplaces["MAYBE"]
        return any([ww in wps.range_night_workplaces for ww in working_workplaces])

    @property
    def min_night_shifts(self):
        """
        The minimal number of night shifts depends on the worker's status.
        """
        min_shifts_dict = {
            "1. leto specializacije"    :   0,
            "2. leto specializacije"    :   5,
            "3. leto specializacije"    :   4,
            "4. leto specializacije"    :   3,
            "5. leto specializacije"    :   2,
            "6. leto specializacije"    :   1,
            "Manj kot 6 mesecev do specialističnega izpita" : 0,
            "Specialist" : 0
        }
        return min_shifts_dict[self.status]

    @property
    def year_of_specialization(self):
        """
        Status is a complicated string, but it is determined by
        the year of specialization.
        """
        status_to_year_dict = {
            "1. leto specializacije"    :   1,
            "2. leto specializacije"    :   2,
            "3. leto specializacije"    :   3,
            "4. leto specializacije"    :   4,
            "5. leto specializacije"    :   5,
            "6. leto specializacije"    :   6,
            "Manj kot 6 mesecev do specialističnega izpita" : 6,
            "Specialist" : 6

        }
        return status_to_year_dict[self.status]


    def __repr__(self):
        return self.name
