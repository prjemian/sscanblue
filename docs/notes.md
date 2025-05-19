# Predevelopment notes

These notes were written before developing the application.

## Bluesky daemon for EPICS/synApps sscan

While demonstrating the `nbs-viewer` GUI, Joe was considering how best
to support APS beam lines that use the EPICS `sscan` record.  These beam
lines do not use bluesky now.  The nbs-viewer can view live Bluesky data (but not live PVs).

Joe was imagining a complete, minimal-effort solution that starts with a
configured scan record and results in live data visualization. The bluesky
integration should be as transparent as possible. Data saved in MDA files is up
to the user. The solution could include saving data to Bluesky storage.  This
solution would allow us to exchange the now-unsupported scanSee, sview, dview,
and mdaviz packages in addition to offering a migration path to Bluesky.

I can see how to work that up.  It would be a truly minimal setup, probably run
as a daemon that monitors a start PV (and also a panic stop PV).  When start
goes True, then initiates a bluesky run of the configured scan record,
outputting data as configured.  Live data tool, such as this viewer, could
visualize.  The tool could (by default, could opt out) send the stream to
storage, as well.

Additional generations would provide:

- Higher dimensionality (scan1, scan2, scan3, scan4, & scanH)
- Bluesky configuration of the sscan record might best be done with a standard
  deployment as a BITS instrument.

## 1-D scans

Simplest case is the 1-D sscan since that makes the least assumptions (can use
`apstools.synApps.SscanRecord`). Multi-dimensional sscans require some
assumptions (made by `apstools.synApps.SscanDevice`).

User provides PVs for the sscan record and the busy record.  When user sets
busy (puts a 1), support sets up the ophyd and bluesky structures according to
the EPICS configuration and starts a run with its `RE`.  When the sscan.FAZE
goes back to zero, the scan is done and support clears busy.  Data is captured
either point-by-point (scan mode: `"LINEAR"` or `"TABLE"`) or at scan end (scan
mode: `"FLY"`).

## Queueserver

It's not possible to run a bluesky plan using `RE(some_plan)` where that call is
placed within a device.  A programmatic way to make this happen is to run the
plan as a task in the queueserver (QS) server.

- User configures the scan record
  - sscan record could save to MDA file via save_data in the IOC
- User sets busy record
- Python process (a QS client):
  - receives the CA monitor event
  - Validates sscan record configuration
  - Queues the `sscan_1D_plan()` plan to the QS server.
  - Starts plan processing in the QS server.
  - `RE` publishes data to subscribers (all are optional)
    - `0MQ` for live data plotting with `nbs-viewer`
    - databroker (and bluesky data storage)
    - SPEC data file
    - NeXus data file
    - tiled data server (sometime in the near future)
  - Resets the busy record once sscan is done
- User can abort scan early by setting busy record to zero or aborting sscan record

## Command-line program `sscan1blue.py`

- User configures the scan record
  - sscan record could save to MDA file via save_data in the IOC
- User runs `sscan1blue.py`
  - Validates sscan record configuration
  - Runs `RE(sscan_1D_plan())`
  - `RE` publishes data to subscribers (all are optional)
    - `0MQ` for live data plotting with `nbs-viewer`
    - databroker (and bluesky data storage)
    - SPEC data file
    - NeXus data file
    - tiled data server (sometime in the near future)
  - Resets the busy record once sscan is done
- User can abort scan early by aborting sscan record.
