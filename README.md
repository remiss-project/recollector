# recollector

Eina per a descarregar tweets que continguin alguns mots clau en diverses finestres temporals,
sense necessitat de preocupar-se per partir les consultes entre Search i Stream.

## Instal·lació

Descarregueu el fitxer `main.py` i instal·leu [twarc](https://github.com/docnow/twarc):
```
pip3 install twarc
```

## Configuració

Heu de configurar twarc i dir-li les vostres claus de l'API de Twitter:
```
twarc2 configure
```

## Ús

Creeu un json amb el següent format:
```
[
  {
    "start-time": "2023-02-02",
    "end-time": "2023-02-02T14:30:37",
    "keywords": ["ProvaCollector", ...]
  },
  ...
]
```

És una llista de finestres temporals que voleu descarregar.
Cada finestra temporal ha de tenir tres atributs:
- `start-time`: El temps d'inici en format ISO i amb el fus horari UTC.
  Pot tenir qualsevol precisió, però com a molt es té en compte fins al segon.
- `end-time`: El temps final, en el mateix format que l'altre.
- `keywords`: Una llista de mots clau que han de contenir els tweets a descarregar.
  La consulta final serà un `OR` de tots ells.
  Si voleu fer consultes més complexes, com `(Prova1 Prova2) OR Prova3`,
  podeu fer `["(Prova1 Prova2)", "Prova3"]`.
  Si voleu aprendre com fer consultes complexes,
  podeu consultar [la documentació de Twitter](https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query)
  o [una guia feta per Igor Brigadir](https://github.com/igorbrigadir/twitter-advanced-search/blob/master/README.md).


Per començar a descarregar tweets, feu:
```
python3 main.py config.json results_
```

Els tweets es desaran en fitxers anomenats `results_search-n.jsonl` o
`results_stream-n.jsonl`.

Les finestres temporals del passat es traduiran a una consulta Search.
Les finestres temporals que continguin el moment actual es convertiran a una consulta Stream
i una consulta Search que tindrà de temps final el moment actual.
Les finestres temporals futures no s'executaran, de moment.

Cada minut es rellegirà el fitxer i s'aplicaran els canvis que calgui.
Això inclou:
- Que la finestra temporal que conté el moment actual arribi a la seva fi,
  o que s'hagi eliminat del fitxer.
  En aquest cas, s'eliminaran tots els mots clau la consulta Stream.
- Que s'arribi a una nova finestra temporal.
  En aquest cas, se n'afegiran els mots clau a la consulta Stream.
- Que s'afegeixi una nova finestra temporal del passat,
  o s'afegeixi un mot clau a una que ja existeix.
  En aquest cas, s'iniciarà una nova consulta Search amb els mots nous.
- Que s'afegeixi una nova finestra temporal que contingui el moment actual,
  o que s'afegeixi un mot clau a la que ja existeix.
  En aquest cas, s'afegiran els nous mots clau a la consulta Stream
  i s'iniciarà una nova consulta Search amb els mots claus nous i amb temps final el moment actual.

Per tal d'evitar descarregar dos cops el mateix tweet,
quan s'afegeix un mot clau nou a una finestra ja existent,
la consulta no demana senzillament els tweets amb el nou mot clau,
sinó els tweets amb el nou mot clau que no contingui cap mot clau que ja haguéssim demanat.

Si voleu que el fitxer es rellegeixi cada, per exemple, 30 segons, feu:
```
python3 main.py config.json results_ --sleep 30
```

Per aturar l'execució, podeu fer CTRL+C.
Si teniu una consulta Stream en execució, s'aturarà.
Les consultes Search s'aturen elles soles quan han recollit tots els tweets.
En aturar l'execució es crea un fitxer `log.json`.
Si voleu reprendre-la sense tornar a descarregar allò que ja heu descarregat,
només cal que mantingueu aquest fitxer al directori on executeu el codi.

## FAQ

1. **Al fitxer de configuració, cal que les finestres temporals siguin disjuntes?**

   No. El programa treballa amb finestres temporals disjuntes i ordenades de la més antiga a la més nova.
   Si seguiu aquest estil tindreu un fitxer de configuació més ordenat.
   Però si no ho feu, no passa res, perquè el programa ja ho convertirà internament al seu format.

2. **Per què hauria de tenir un fitxer amb dues finestres si puc executar senzillament el codi dos cops amb un fitxer diferent per cada execució?**

   Per si les dues finestres se solapen.
   Per exemple, suposem que volem descarregar els tweets amb el mot "Prova1"
   publicats entre el 2010 i el 2020.
   I també volem els tweets amb el mot "Prova2" publicats entre el 2018 i 2019.
   Si ho fem en dues execucions diferents,
   els tweets publicats entre el 2018 i el 2019 i que continguin els dos mots
   seran descarregats dos cops, un per cada execució.
   En canvi, utilitzant un sol fitxer, els tweets serien descarregats un sol cop.
