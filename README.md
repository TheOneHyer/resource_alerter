resource_alerter
================

!!!WARNING!!!: resource_alerter has not yet been tested

resource_alerter is package containing two simple to use scripts to create
and run resource_alerted: a Python daemon for Unix-like systems that monitors
system resource usage and alerts users to high usage.

Quick Start
-----------

> pip install resource_alerter
>
> sudo resource_alerter_setup.py --force-yes
>
> sudo resource_alerterd.py start

*Note: You MUST run the setup script before the daemon. If you do not the 
daemon will not function and you will get cryptic errors.*

Synopsis
--------

As aforementioned, resource_alerterd is a Python daemon for Unix-like systems
that monitors system resource usage and alerts users to high resource usage.
More specifically, resource_alerted monitors CPU, RAM, and IO Wait and logs 
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

> 1. Read in logging configuration file
> 2. Create loggers
> 3. Read in daemon configuration file
> 4. Initialize daemon
> 5. See if 'wall' is available for broadcasts
> 6. Calculate max IO Wait as 100.0 / # of cores
> 7. Start infinite loop
> 8. Calculate similarity to PID list of last resource check
> 9. Reset last PID list w/ current one
> 10. for RESOURCE in CPU, RAM, IO Wait:
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

    Minimum amount of time between CPU-usage override activates in seconds. 
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
    
* io_check_delay:

    Approximate time between IO usage checks in seconds.
    
* io_critical_level:

    Lower IO usage percent threshold for declaring IO usage critical,
    i.e. IO usage above this value is deemed critical.
    
* io_override_delay:

    Minimum amount of time between IO-usage override activates in seconds. 
    Essentially, high IO usage will trigger a broadcast roughly at least as 
    often as this value.
    
* io_stable_diff:

    Max *PERCENTAGE POINT* (not percent) difference between last IO usage 
    broadcast and current IO usage before IO usage is declared unstable. 
    IO usage must be unstable to enable broadcasting unless the IO-usage 
    override is active.
    
* io_warning_level:

    Lower IO usage percent threshold for declaring IO usage warning,
    i.e. IO usage above this value is deemed worth broadcasting a warning.
    
* min_pid_same:

    Minimum percent similarity permitted between current Process IDs and 
    Process IDs of last resource check (not broadcast). Anything percent 
    similarity below this value will allow the resource check to continue, 
    anything above this value will skip the resource checks.
   
* ram_check_delay:

    Approximate time between RAM usage checks in seconds.
    
* cpu_critical_level:

    Lower RAM usage percent threshold for declaring RAM usage critical,
    i.e. RAM usage above this value is deemed critical.
    
* ram_override_delay:

    Minimum amount of time between RAM-usage override activates in seconds. 
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
  1) Disable PID similarity check: set min_pid_same to "0.0"
  2) Disable resource time delay: set [resource]_check_delay to "0.0" (this
    causes resource_alerted to more or less continuously monitor and log 
    [resource], not recommended)
  3) Disable resource stability check: set [resource]_stable_diff to "0.0"
  4) Disable all filters: set [resource]_override_delay to "0.0" (see point
    2 for why this isn't recommended)
    
* While you cannot directly disable checking a specific resource, you can  
effectively disable a resource's broadcasts, by setting 
[resource]_warning_level and [resource]_critical_level to "100.1" or higher.
*Note: this does not guarantee that the IO resource check won't broadcast 
(though it'll mostly do the job) because the IO max usage is not 100% IO Wait
but rather (100.0 / # of cores), setting the IO warning and critical levels to
(100.0 * # of cores + 0.1) will guarantee that the IO usage broadcast is 
disabled.*
