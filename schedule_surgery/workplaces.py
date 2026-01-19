"""
Contains some data that is needed all over the package.
"""

STANDARD_WORKPLACES = [
    "KRG 1",
    "KRG 2",
    "KRG 3",
    "KRG 4",
    "KRG 5",
    "KRG N - B",
    "KRG N - MOP",
    "KRG N - ABD",
]

UNCONNECTED_WORKPLACES = [
    "ABDOMEN",
    "ABD prip.",
    "TRAVMA"
    ]

ALL_WORKPLACES = STANDARD_WORKPLACES + UNCONNECTED_WORKPLACES

NIGHT_WORKPLACES = ALL_WORKPLACES[5:8]

range_day_workplaces = range(0, 5)
range_night_workplaces = range(5, 8)
range_connected_workplaces = range(0, 8)
range_unconnected_workplaces = range(8, 11)

def get_ndx(name : str) -> int:
    return ALL_WORKPLACES.index(name)

b_day_ndx = get_ndx("KRG 1")
abd_day_ndx = get_ndx("KRG 2")
mop_day_ndx = get_ndx("KRG 3")

b_night_ndx = get_ndx("KRG N - B")
mop_night_ndx = get_ndx("KRG N - MOP")
abd_night_ndx = get_ndx("KRG N - ABD")
