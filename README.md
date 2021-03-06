resource_alerter
================

Version: 1.0.0

resource_alerter is package containing a simple to use script to run 
resource_alerted: a Python daemon for Unix-like systems that monitors
system resource usage and alerts users to high usage.

ra_daemon
---------

A quick note: the package ra_daemon is just python-daemon v2.10 
copied-and-pasted with a single error fixed. This error prevents 
resource_alerterd.py from daemon-izing. I have emailed the developers of 
python-daemon concerning the issue. Once they fix it, I will delete this 
package and just import python-daemon again.

Quick Start
-----------

> pip install resource_alerter
>
> sudo resource_alerterd.py start
>
> sudo resouce_alerterd.py --systemd  # For use with unit scripts in systemd

Synopsis
--------

As aforementioned, resource_alerterd is a Python daemon for Unix-like systems
that monitors system resource usage and alerts users to high resource usage.
More specifically, resource_alerted monitors CPU and RAM and logs 
resource use if it crosses a "warning" and/or "critical" threshold. The 
daemon is also capable of sending out a broadcast via the "wall" program
if present. Obviously there are a few problems with sending out a broadcast
every time a resource crosses the threshold, e.g. a program hovering around
80% CPU usage, which is the "warning threshold" for this example, may dip above
and below the threshold many times in rapid succession and thus trigger 
numerous consecutive broadcasts. As such, this daemon sports an algorithm 
for deciding whether or not it should actually send a broadcast when it detects
high resource usage. All of this is explained in the config options and 
algorithm sections below.

Algorithm
---------

The following algorithm summarizes all steps performed by resource_alerted. 
The text-image after the algorithm visualizes the filters that determine 
whether or not a high usage broadcast needs to be made in Step 10.

###Algorithm

> 1. Read and parse logging configuration file
> 2. Create loggers
> 3. Read and parse daemon configuration file
> 4. Initialize daemon
> 5. See if 'wall' is available for broadcasts
> 7. Start infinite loop
> 8. Calculate similarity to PID list of last resource check
> 9. Replace last PID list w/ current one
> 10. for RESOURCE in CPU, RAM:
>   * Calculate time since RESOURCE override last active, activate if too 
> long
>   * Skip RESOURCE check if PID similar and override inactive
>   * Calculate time since last RESOURCE check
>   * Perform RESOURCE check if too long since last check or override active
>   * Obtain RESOURCE usage
>   * See if RESOURCE usage has changed significantly since last 
> log/broadcast
>   * If RESOURCE usage deemed "unstable" and above threshold, log/broadcast
>   * If broadcast, reset "stability" reference point to current RESOURCE usage
>   * Reset last RESOURCE check time to current time
> 11. Calculate time to sleep until next resource check
> 12. Sleep until next resource check

### Visual Summary - Step 10 ###

    |----------|      |------------|      |----------|      |-----------|      |----------|      |-----------|
    |          | ---> |            | ---> | Time for | ---> | Resource  | ---> | Resource | ---> | Broadcast |
    | Resource | ---> |    PID     | ---> | Resource | ---> |           | ---> | Use High |      |-----------|
    |          | ---> |            | ---> |  Check   | ---> | Stability |      |----------|
    |          | ---> | Similarity | ---> |          |      |-----------|           ^
    |  Check   | ---> |            |      |----------|                              |
    |          |      |------------|                                                |
    |----------| -------------------> |First Check or Override| --------------------

Configuration File Options
--------------------------

resource_alerterd requires two config files to function: resource_alerted
.conf and resource_alerted.logging.conf. The prior files contains options 
that control various steps in resource_alerterd's algorithm and the latter 
contains the information required to handle the logs. Config options are 
described below followed by a tip-and-tricks segment.

### Logging Config Options ###

The log file uses and follows the requirements of the 
[Python logging module](https://docs.python.org/2/library/logging.html). Any
and all details on this module can be found in the link.
 
### Config Options ###

The main config file has many useful options that change how often 
resource_alerted broadcasts on a variety of levels. Each option is described
below:

* cpu_check_delay:

    Approximate time between CPU usage checks in seconds.
    
* cpu_critical_level:

    Lower CPU usage percent threshold for declaring CPU usage critical,
    i.e. CPU usage above this value is deemed critical.
    
* cpu_override_delay:

    Minimum amount of time between CPU-usage overrides in seconds. 
    Essentially, high CPU usage will trigger a broadcast roughly at least as 
    often as this value.
    
* cpu_stable_diff:

    Max *PERCENTAGE POINT* (not percent) difference between last CPU usage 
    broadcast and current CPU usage before CPU usage is declared unstable. 
    CPU usage must be unstable to enable broadcasting unless the CPU-usage 
    override is active.
    
* cpu_warning_level:

    Lower CPU usage percent threshold for declaring CPU usage warning,
    i.e. CPU usage above this value is deemed worth broadcasting a warning.
    
* critical_wall_message:

    True or False. If True and your system has the program 'wall', critical 
    resource use will be both broadcast and logged. If false or your 
    system doesn't have the program 'wall', critical resource use will only 
    be logged.
    
* min_pid_same:

    Minimum percent similarity permitted between current Process IDs and 
    Process IDs of last resource check (not broadcast). Anything percent 
    similarity below this value will allow the resource check to continue, 
    anything above this value will skip the resource checks unless
    overrides are active.
   
* ram_check_delay:

    Approximate time between RAM usage checks in seconds.
    
* cpu_critical_level:

    Lower RAM usage percent threshold for declaring RAM usage critical,
    i.e. RAM usage above this value is deemed critical.
    
* ram_override_delay:

    Minimum amount of time between RAM-usage overrides in seconds. 
    Essentially, high RAM usage will trigger a broadcast roughly at least as 
    often as this value.
    
* ram_stable_diff:

    Max *PERCENTAGE POINT* (not percent) difference between last RAM usage 
    broadcast and current RAM usage before RAM usage is declared unstable. 
    RAM usage must be unstable to enable broadcasting unless the RAM-usage 
    override is active.
    
* ram_warning_level:

    Lower RAM usage percent threshold for declaring RAM usage warning,
    i.e. RAM usage above this value is deemed worth broadcasting a warning.
    
* warning_wall_message:

    True or False. If True and your system has the program 'wall', 
    warning-level resource use will be both broadcast and logged. If false 
    or your  system doesn't have the program 'wall', warning-level resource 
    use will only be logged.

### Config Tips-and-Tricks ###

* While you cannot directly disable the various filters used in Step 10 to 
limit unnecessary broadcasts, certain config settings will effectively 
disable the filters:
>  * Disable PID similarity check: set min_pid_same to "0.0"
>  * Disable resource time delay: set [resource]_check_delay to "0.0" (this
>    causes resource_alerted to more or less continuously monitor and log 
>    [resource], not recommended)
>  * Disable resource stability check: set [resource]_stable_diff to "0.0"
>  * Disable all filters: set [resource]_override_delay to "0.0" (see point
>    2 for why this isn't recommended)
    
* While you cannot directly disable checking a specific resource, you can  
effectively disable a resource's broadcasts, by setting 
[resource]_warning_level and [resource]_critical_level to "100.1" or higher.

* To save on resource use by the daemon or high log turnover, tune the 
[resource]_check_delay and [resource]_override_delay to fit your preferences.

Important Notes
---------------

* It is highly advised that resource_alerted is started at boot. 
Accomplishing this is often unique to your operating system.

* You must run resource_alerterd.py as root for proper functionality.

Unit File
---------

An example unit file for use with systemd that should work on most systems
is included in this package: [resource_alerterd.service](resource_alerterd.service).