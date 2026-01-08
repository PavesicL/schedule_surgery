# schedule_surgery

A schedule generator tuned for the surgery departement of UKC LJ.

# Installation

TODO

# Input

The input to the program are three files:
- seznam zelja, v formatu .tsv.
- master sheet, kjer je oznaceno na katerih deloviscih dela specializant, in koliko dezurstev se mu oprosti. Format .tsv.
- delno izpolnjen urnik; kot prosti se vpostevajo le tisti termini, ki so na tem urniku prazni. Osebe, ki so ze vpisane v urnik, se ne razpisejo dodatno.
- config.json, z zacetnim in koncnim datumom, in modelskimi utezmi.

Glej examples/ za primer.

## config.json

V config.json morajo biti sledeca polja:
- "start_date", "end_date": datum zacetka in konca urnika, vkljucno s tema dvema datumoma. V formatu YYYY-MM-DD.
- "krozeci_scheduled": kolikokrat naj bo v urnik vpisan vsak specializant s statusom "KROZECI".
- "workplace_weights": slovar utezi za razlicna delovna mesta: {"workday" : 15, "weekend" : 4, "night_1" : 1, ..., "night_6" : 3 }. Workload delavca se izracuna kot vsota: workplace_weight * times_scheduled_at_workplace.

Utezi za objective function (vse naj bodo pozitivna cela stevila):
- "preferential_assignment_day": jakost utezi na to, da delavec dela na dan, ko zeli.
- "weight_equal_workload": jakost utezi na enakomerno razporejen workload.
- "weight_consecutive_nights": jakost utezi na zaporedne nocne izmene. 
- 

# Model

Vsak dan imamo pet dnevnih delovisc (KRG-B, KRG-ABD, KRG-MOP, KRG4, KRG5), tri nocna delovisca (KRG-B-N, KRG-MOP-N, KRGN-ABD-N), in pripravljenost ABD-PRIP. 
Na vsako je razpisana tocno ena oseba. 

## Hard constraints

- Iz nocnega delovisca nikoli na dnevno delovisce naslednji dan.
- Na delovne dni iz dnevnega delovisca nikoli na nocno.
- Stevilo nocnih izmen na mesec je omejeno od spodaj glede na leto specializacije, in od zgoraj s 5 - (stevilo oproscenih dezurnih).
- Vikend, ce oseba dela na nocnih deloviscih: najvec en vikend dan na mesec na dnevnem in nocnem deloviscu, od tega mora tocno eno biti MOP.
- Vikend, ce oseba ne dela na nocnih deloviscih: najvec en vikend na mesec, oba dni zapored. 

## Soft constraints

- Dve nocni izmeni zapored.
- Specializanti v kategoriji KROZECI so razporejeni na urgenco (???) najmanj dvakrat na mesec.


## Cost function

Utezi, ki jih minimiziramo:
- Enakomerna obremenitev overall: za vsakega specializanta se izracuna mesecna obremenitev, ki naj bo cim bolj enakomerna. Razlicno so obtezena nocna delovisca, dnevna delovisca in dnevna vikend delovisca. Obtezitev nocnih izmen je odvisna od letnika specializacije.
- Enakomerna obremenitev za ABD-PRIP: med tistimi, ki delajo na ABD-PRIP, naj bodo razpisani cim bolj enakomerno.
 




