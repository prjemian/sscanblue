# User Guide

The EPICS [sscan](https://github.com/epics-modules/sscan) record (part of
[synApps](https://github.com/EPICS-synApps)) is in common use at the Advanced
Photo Source.  It provides a complete data acquisition package from the EPICS
IOC.

## Background

Here is an example control screen for the sscan record `gp:scan1`, configured to
run a step-wise (`LINEAR`) scan of scaler `gp:scaler1` v. motor `gp:m1`.

![example sscan control gui](./sscan1.png)

To execute the sscan, press the SCAN button and wait for the sscan to execute.
In the example shown, data from the most recent scan was written to file
`gp_0069.mda`.

See the [documentation](https://epics.anl.gov/bcda/synApps/sscan/sscanDoc.html)
for more details about the sscan record and how to use it.

## Executing 1-D Linear and Table scans

Simplest case is the 1-D sscan since that makes the least assumptions, using [`SscanRecord`](https://bcda-aps.github.io/apstools/latest/api/synApps/_sscan.html#apstools.synApps.sscan.SscanRecord) (from apstools).

NOTE:  At its current stage of development, the code is only prepared to use sscan records configured for one-dimensional data collection.

Using a pre-configured sscan record, the `sscan1blue` application will execute
the scan and publish the data step-by-step to all configured subscribers
(default includes a [ZMQ](https://zeromq.org/) socket for live data viewing and
a temporary databroker catalog).  Additional command-line options allow for
storing data to other locations (MongoDB-backed database, NeXus HDF5 file, and
SPEC text file).

User provides PV for the sscan record.  This support sets up the
ophyd and bluesky structures according to the EPICS configuration and starts a
run with its bluesky `RE`.  When the sscan.FAZE goes back to zero, the scan is done.
Data is captured either point-by-point (scan mode: `"LINEAR"` or `"TABLE"`) or
at scan end (scan mode: `"FLY"`).

For now, this code handles only LINEAR and TABLE modes.  Data is acquired
point-by-point.  No data arrays are collected from the sscan record.

### Examples

Perhaps a simple example, then a full example.

#### Simple

Execute the EPICS sscan record `gp:scan1`.  Print a table of data to the console.

```python
sscan1blue -v gp:scan1
```

#### Full-featured

Same as above plus add metadata, set the `scan_id`, write NeXus and SPEC files,
write documents to the Bluesky databroker catalog `my_data_catalog`, and be
explicit about publishing data to ZMQ.

```python
sscan1blue.py gp:scan1 \
    -c my_data_catalog \
    -m '{"title": "test of sscan1blue", "scan_id": 25}' \
    -n nexus.h5 \
    -s spec.dat \
    -z localhost:5567 \
    -v
```

### LIVE DATA PLOT

To plot live data, first start these two processes in a separate console:

* ``nbs-viewer -d &`` (and open a new ZMQ data source)
  * Once started, choose "New Data Source", then "ZMQ"
* ``bluesky-0MQ-proxy 5567 5578``
