DraveMotion v0.40  —  een Dravenlock product
============================================

Een portable animatie- & videostudio. Alles blijft in deze map
(instellingen, cache, projecten). Niets in Windows-systeemmappen,
dus je kunt de hele map gewoon op een USB-stick meenemen.


STARTEN (Windows)
-----------------
Dubbelklik op:   run.bat

De eerste keer installeert hij zichzelf eenmalig in de map ".venv"
(daar heb je internet voor nodig). Daarna start hij gewoon op,
ook zonder internet.

Heb je nog geen Python? Installeer Python 3 van
https://www.python.org/downloads/ en vink bij de installatie
"Add python.exe to PATH" aan. Start daarna run.bat opnieuw.


WAT ZIT ER IN DEZE MAP
----------------------
  run.bat            <- hiermee start je (dubbelklik)
  herstel.bat        <- start niet op? Dubbelklik dit (zie hieronder)
  dravemotion.py     <- het programma zelf
  requirements.txt   <- lijst met benodigde pakketten
  README.txt         <- dit bestand

Na de eerste start verschijnen vanzelf:
  .venv\             <- de lokale, portable installatie
  cache\             <- tijdelijke bestanden (mag je leeghalen)
  projecten\         <- je opgeslagen projecten en exports
  logo.ico / logo.png<- (optioneel) zet hier je eigen app-icoon neer
  bin\ffmpeg.exe     <- (optioneel) eigen ffmpeg voor 100% offline MP4


KORT OVERZICHT
--------------
  * Tijdlijn met meerdere sporen; bovenste spoor wint. Sleep de rode
    afspeelkop (of de tijdbalk) om te scrubben. Rechtsklik op een clip om
    hem te knippen (grijze stippellijn).
  * Media bestanden links: importeer losse video/foto/audio OF laad een hele
    map in een keer (bv. een soundpool) met "Map laden...". Submappen worden
    uitklapbare groepen; klik een mapnaam open. Sleep een bestand op de tijdlijn
    of dubbelklik om het te plaatsen.
  * Tekenscene en Tekst/titel via de knoppen. Tekst: lettertype, grootte,
    breedte, kleur; versleep de tekst in het voorbeeld om te verplaatsen.
  * Per clip: positie, schaal, rotatie en opaciteit — met keyframes (◆)
    om die over tijd te animeren.
  * Effecten per beeldclip: helderheid, contrast, verzadiging, vervaging
    en een kleurfilter (grijs/sepia/negatief).
  * Transities per clip: fade, schuiven, vegen, zoom, dip naar zwart/wit;
    overlappende clips lopen in elkaar over (crossfade). Audio: volume + fades.
  * Snelheid / timelapse per videoclip (slow motion t/m versneld).
  * Export naar MP4 (met geluid), GIF of een PNG-reeks.

Sneltoetsen:
  Spatie        afspelen / pauze
  Ctrl+Z        ongedaan
  Ctrl+Y        opnieuw
  Ctrl+D        clip dupliceren
  Delete        clip verwijderen
  Ctrl+scroll   in-/uitzoomen op de tijdlijn

In de app vind je rechtsboven een uitgebreidere Snelgids.


START NIET OP? (probleemoplossing)
----------------------------------
1. Dubbelklik op  herstel.bat . Dat gooit de lokale installatie weg en
   zet hem schoon opnieuw op. Je projecten blijven staan.

2. Helpt dat niet, kijk dan in het bestand  start-log.txt  dat naast
   run.bat verschijnt. Daar staat precies wat er misging. Stuur dat
   bestand door, dan zoek ik het uit.

Veelvoorkomende oorzaak: Python ontbreekt of staat niet in PATH.
Installeer Python 3 van https://www.python.org/downloads/ en vink
"Add python.exe to PATH" aan.

LET OP - Python 3.14 is nog TE NIEUW voor PyQt5. Heb je alleen 3.14,
installeer dan Python 3.13 erbij (3.14 mag blijven staan):
   https://www.python.org/downloads/release/python-31313/
Kies "Windows installer (64-bit)" en vink "Add python.exe to PATH" aan.
run.bat kiest daarna vanzelf de juiste versie.



CONTACT & UPDATES
-----------------
  * Rechtsboven in de app:
      "✉️ Contact"  — stel een vraag, meld een klacht/idee of een bug.
                       Het opent je e-mailprogramma met een bericht klaar
                       aan service@dravenlock.nl.
      "🔄 Updates"  — controleert of er een nieuwere versie is.

  Bij het opstarten kijkt DraveMotion kort of er een update is en meldt dat
  alleen als er echt een nieuwere versie klaarstaat. De nieuwste versie vind
  je op https://dravenlock.nl/downloads/DraveMotion/


EEN ZELFSTANDIGE .EXE MAKEN (alles erin, geen losse bestanden)
--------------------------------------------------------------
  1. Zet (optioneel) je logo.ico in deze map -> wordt het .exe-icoon.
  2. Dubbelklik  bouw-exe.bat
  3. Klaar -> EEN bestand:  dist\DraveMotion.exe
     De app maakt config/projecten/cache zelf aan naast de .exe.

  Wat zit er IN de .exe: PyQt5, numpy, opencv, Pillow, soundfile EN ffmpeg
  (voor MP4-export) - alles ingebouwd, geen losse bestanden nodig.
  NIET erin: de stem (NeuVoice/TTS) - die draait via een aparte Python en
  haalt het model online op; gebruik daarvoor run.bat. De .exe meldt dit netjes.

  Gebruik je je eigen py->exe+setup+uninstaller-tool? Prima: de app vindt ffmpeg
  zowel als het IN de .exe is gebundeld (onefile) als los in een bin-map.

Veel plezier ermee.  — gemaakt voor Dravenlock


Stem (tekst-naar-spraak)
------------------------
Met de knop "Stem (tekst-naar-spraak)" maak je met NeuVoice (lokaal, via ONNX) een
gesproken stem van je tekst: kies stem, taal, snelheid en kwaliteit, voeg eventueel
emotie-tags toe (<happy>, <sad>, <laugh>, <breath>), beluister en sla op als MP3 in de
map "media". Het bestand verschijnt in Media bestanden onder "Stemmen (TTS)" en kun je
naar de tijdlijn slepen. De eerste keer wordt het stemmodel automatisch gedownload.
