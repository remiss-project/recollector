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

Twitter només pot executar una consulta Stream alhora.
Per tant, per tal de poder fer dues consultes alhora al recol·lector,
cal que almenys una d'elles no faci cap consulta Stream.
En aquest cas, feu:
```
python3 main.py config.json results_ --no-stream
```

## FAQ

1. **Per què hauria de tenir un fitxer amb dues finestres si puc executar senzillament el codi dos cops amb un fitxer diferent per cada execució?**

   Per si les dues finestres se solapen.
   Per exemple, suposem que volem descarregar els tweets amb el mot "Prova1"
   publicats entre el 2010 i el 2020.
   I també volem els tweets amb el mot "Prova2" publicats entre el 2018 i 2019.
   Si ho fem en dues execucions diferents,
   els tweets publicats entre el 2018 i el 2019 i que continguin els dos mots
   seran descarregats dos cops, un per cada execució.
   En canvi, utilitzant un sol fitxer, els tweets serien descarregats un sol cop.

2. **On puc revisar si una consulta no s'ha executat per algun error?**

   Al log de Twarc corresponent, que serà de la forma `search-x.log` o `stream-x.log`.
   Els errors que apareixen en aquests fitxers són errors que el recol·lector no ha detectat,
   com el que us sortiria si us revoquessin el permís d'accés a l'API.
   Com que l'error no es detecta, a l'hora d'escriure el log del recol·lector (`log.json`)
   es considera que la consulta s'ha executat.
   És per això que si veieu un error així haureu d'arreglar el log manualment:
   Caldrà que esborreu del log els mots clau o les finestres que no s'han descarregat per culpa de l'error.
   Llavors podreu tornar a executar la consulta si l'error original s'ha solucionat
   i us descarregarà els tweets que faltin.

3. **Quina llargada poden tenir les consultes?**

   Twitter imposa que les consultes no poden superar els 1024 caràcters.
   Si els mots clau que poseu al vostre fitxer de configuració (el `config.json`, si l'anomeneu així) superen el límit,
   el recol·lector us avisarà i us demanarà que ho arregleu.

   Ara bé, si heu modificat o eliminat algun mot clau del fitxer de configuració quan ja l'havíeu descarregat,
   aquest mot clau continua al log (`log.json`).
   I el recol·lector fa servir el log per fer les consultes de Twarc per evitar descarregar tweets repetits.
   Això pot fer, doncs, que una consulta passi la revisió del recol·lector,
   que es basa en el fitxer de configuració,
   però Twitter la rebutgi igualment perquè el log l'ha feta més llarga.

   Si passa això, ho haureu d'arreglar manualment.
   Primerament, eliminant del log allò que no s'ha descarregat per culpa de l'error,
   tal com dèiem al punt anterior.
   Però també haureu d'arreglar l'origen de l'error,
   ja sigui esborrant mots clau del fitxer de configuració (i, per tant, renunciant a descarregar més tweets)
   o bé esborrant els mots clau no desitjats del log (i, per tant, arriscant-se a descarregar tweets repetits).
   En cas que decidiu això segon, us recomanem que
   apunteu igualment quins mots clau heu esborrat i de quines finestres temporals eren,
   ja que si ho esborreu del log ja no estarà registrat enlloc més.

   Aquest problema també el podeu trobar si feu servir finestres temporals que no són disjuntes,
   perquè el recol·lector en crea una que és la intersecció temporal amb la unió dels mot clau,
   per evitar descarregar tweets repetits.
   Llavors, la consulta final podria ser massa llarga
   encara que les dues originals fossin prou curtes.
   En aquest cas, també ho haureu d'arreglar manualment,
   esborrant algun dels mots clau.

4. **Al fitxer de configuració, cal que les finestres temporals siguin disjuntes?**

   No és obligatori, però us ho recomanem.
   El programa treballa amb finestres temporals disjuntes i ordenades de la més antiga a la més nova.
   Si seguiu aquest estil tindreu un fitxer de configuació més ordenat.
   Si no ho feu i les consultes no són excessivament llargues,
   no passa res, perquè el programa ja ho convertirà internament al seu format.
   Ara bé, si les consultes fossin llargues i les finestres no les féssiu disjuntes,
   us podríeu trobar amb els problemes descrits a la qüestió 3.

5. **Puc esborrar o modificar del fitxer de configuració un mot clau que ja he descarregat de forma parcial o total?**

   Us recomanem que no n'esborreu, per evitar els problemes descrits a la qüestió 3.

   Si ja l'heu descarregat totalment,
   esborrar-lo no us estalviarà de descarregar cap tweet.
   I a més, si el manteniu, el fitxer de configuració us servirà per
   explicar correctament com s'han descarregat tots els tweets.

   Si només l'heu descarregat parcialment,
   el que podeu fer és aturar la consulta Stream
   i partir en dos la finestra temporal de la configuració
   pel punt on heu aturat la consulta.
   A la primera part, podeu mantenir el mot clau pels motius anteriors.
   I, a la segona part, podeu esborrar el mot per evitar que es descarregui quan torneu a engegar el recol·lector.

   Pel que fa a modificar un mot clau,
   penseu que és el mateix que esborrar l'original i afegir la versió nova.
   Així doncs, si s'ha descarregat parcialment, partiu la consulta com hem dit.
   Si s'ha descarregat, no esborreu el mot original i senzillament afegiu la versió nova.
   Si no s'ha descarregat, modifiqueu tranquil·lament el mot.
