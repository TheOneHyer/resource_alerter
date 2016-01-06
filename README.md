resource_alerter
================

!!!WARNING!!!: resource_alerter has not yet been tested

resource_alerter is package containing two simple to use scripts to create
and run resource_alerted: a Python daemon for Unix-like systems that monitors
system resource usage and alerts users to high usage.

Quick Start
-----------

>>>>pip install resource_alerter
>>>>
>>>>sudo resource_alerter_setup.py --force-yes
>>>>
>>>>sudo resource_alerterd.py start

Synopsis
--------

As aforementioned, resource_alerterd is a Python daemon for Unix-like systems
that monitors system resource usage and alerts users to high resource usage.
More specifically, resource_alerted monitors CPU, RAM, and IO Wait and logs 
resource use if it crosses a "warning" and/or "critical" threshold. The 
daemon is also capable of sending out a broadcast via the "wall" program
if present. Obviously there are a few problems with sending out a broadcast
every time a resource crosses the threshold. E.g. a program hovering around
80% CPU usage, which is the "warning threshold" for this example, may dip above
and below the threshold many times in rapid succession and thus trigger 
numerous consecutive broadcasts. As such, this daemon sports an algorithm 
for deciding whether or not it should actually send a broadcast when it detects
high resource usage. All of this is explained in the log options and 
algorithm sections below.

Algorithm
---------

>>>>1. Read in logging configuration file
>>>>2. Create loggers
>>>>3. Read in daemon configuration file
>>>>4. Initialize daemon
>>>>5. See if 'wall' is available for broadcasts
>>>>6. Calculate max IO Wait as 100.0 / # of cores
>>>>7. Start infinite loop
>>>>8. Calculate similarity to PID list of last resource check
>>>>9. Reset last PID list w/ current one
>>>>10. for RESOURCE in CPU, RAM, IO Wait:
>>>>* Calculate time since RESOURCE override last active, activate if too long
>>>>* Skip RESOURCE check if PID similar and override inactive
>>>>* Calculate time since last RESOURCE check
>>>>* Perform RESOURCE check if too long since last check or override active
>>>>* Obtain RESOURCE usage
>>>>* See if RESOURCE usage has changed significantly since last log/broadcast
>>>>* If RESOURCE usage deemed "unstable" and above threshold, log/broadcast
>>>>* If broadcast, reset "stability" reference point to RESOURCE usage
>>>>* Reset last RESOURCE check time to current time
>>>>11. Calculate time to sleep until next resource check
>>>>12. Sleep until next resource check

Log Options
-----------
