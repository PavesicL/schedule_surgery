# schedule_surgery

A schedule generator tuned for the surgery departement of UKC LJ.

# Installation

TODO

# Input

The input to the program are three files:
- seznam zelja, v formatu .tsv.
- master sheet, kjer je oznaceno na katerih deloviscih dela specializant, in koliko dezurstev se mu oprosti. Format .tsv.
- config.json, z zacetnim in koncnim datumom, in modelskimi utezmi.
- delno izpolnjen urnik; kot prosti se vpostevajo le tisti termini, ki so na tem urniku prazni.

Glej examples/ za primer.

# Model

Vsak dan imamo pet dnevnih delovisc (KRG-B, KRG-ABD, KRG-MOP, KRG4, KRG5), tri nocna delovisca (KRG-B-N, KRG-MOP-N, KRGN-ABD-N), in pripravljenost ABD-PRIP. 
Na vsako je razpisana tocno ena oseba. 

## Hard constraints

- Iz nocnega delovisca nikoli na dnevno delovisce naslednji dan.
- Na vikende in praznike iz dnevnega delovisca nikoli na nocno.
- Stevilo nocnih izmen na mesec je omejeno od spodaj glede na leto specializacije, in od zgoraj s 5 - (stevilo oproscenih dezurnih).
- Vikend, ce oseba dela na nocnih deloviscih: najvec en vikend dan na mesec na dnevnem in nocnem deloviscu, od tega mora tocno eno biti MOP.
- Vikend, ce oseba ne dela na nocnih deloviscih: najvec en vikend na mesec, oba dni zapored. 

## Soft constraints

- Dve nocni izmeni zapored.
- Specializanti v kategoriji KROZECI so razporejeni na urgenco (???) najmanj dvakrat na mesec.


## Cost function

Utezi, ki jih minimiziramo:
- Enakomerna obremenitev overall: za vsakega specializanta se izracuna mesecna obremenitev, ki naj bo cim bolj enakomerna. Razlicno so obtezena nocna delovisca, dnevna delovisca in dneva vikend delovisca. Obtezitev nocnih izmen je odvisna od letnika specializacije.
- Enakomerna obremenitev za ABD-PRIP: med tistimi, ki delajo na ABD-PRIP, naj bodo razpisani cim bolj enakomerno.
 




