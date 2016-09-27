MidiGraph
=========

MidiGraph is a MIDI graph inspector for GNU/Linux. It is a tool realized
for developers and MIDI "power" users who need to know a bit more about
the MIDI clients/ports and connections available.

Usually one would use "simpler" tools, such as aplaymidi/arecordmidi
with the "``-l``\ " flag, or patchbays like Patchage or QJackCtl.
MidiGraph shows much more information, which can be useful to better
understand the specification of every MIDI port and connection and
eventually debug external programs.

For instance, it will show *every* MIDI client and port available to
ALSA, even system and hidden ones; The connections (ALSA's
"subscriptions") are graphically shown as actual connections between
ports, with detailed information for each one of them.

Requirements
------------

-  Python 2.7
-  PyQt4 >= 4.11.1
-  pyalsa

Usage
-----

There is not an installation procedure yet, just run the script in the
main directory:

::

    $ ./MidiGraph

The top panel shows the full MIDI graph, allowing filtering between
hardware clients (sound cards, USB MIDI devices) and software clients
(sequencers, virtual instruments). By default the system client and
hidden ports are not shown, use the checkboxes to display them. The port
type and capability panels are hidden on start up, just click on their
relative label to toggle the view.

Future
------

-  JACK support.
-  create/delete connections
-  export client/port specifications to file

Known issues
------------

Sometimes ALSA clients do not report their actual name on startup and
they may show up in the graph as "Client-".
