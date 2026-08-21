
## Author

**Zeyad Mohamed Nashaat Abdelghany Gharaf**

## Maintainer

**Niccolo Izzo**

## Overview

The `trace_capturing` tool is a Python package designed to automate trace acquisition for Side-Channel Analysis (SCA) experiments.

It provides a complete workflow for:

- Configuring and controlling an oscilloscope through PyVISA and SCPI commands
- Capturing single traces, segmented traces, and bucket-based trace sets
- Synchronizing the oscilloscope with a Device Under Test (DUT)
- Loading traces from CSV and HDF5 files
- Generating plaintexts for acquisition campaigns
- Saving and loading metadata associated with captured traces
- Communicating with an external packet generation server through HTTP requests
- Managing standardized error codes and logging

The tool is intended for practical SCA experiments where electromagnetic or power traces are captured from cryptographic operations, such as SHA-256 or HMAC-SHA256, running on a DUT.

---

## Package Files

The `trace_capturing` tool is composed of four main modules that together provide the complete trace acquisition workflow.

### cap_lib.py

This module contains the `Scope` class, which is the main interface between Python and the oscilloscope.

It is responsible for:

- Initializing and controlling the oscilloscope through PyVISA.
- Configuring channels, triggers, and waveform acquisition settings.
- Managing synchronization with the Device Under Test (DUT).
- Performing single-trace, segmented, and bucket-based acquisitions.
- Saving segmented captures directly to the oscilloscope disk.
- Handling low-level SCPI communication and instrument error checking.

This file forms the core acquisition engine of the framework.

---

### utilities.py

This module contains helper classes and functions required throughout the acquisition workflow.

Its functionality includes:

- Configuring and managing logging.
- Loading trace datasets from CSV files.
- Loading trace datasets from HDF5 files.
- Loading complete bucket-based datasets.
- Generating plaintexts for acquisition campaigns.
- Generating fixed-versus-random plaintexts for TVLA experiments.
- Saving metadata into trace files.
- Reading metadata previously stored inside trace files.

This file serves as the primary data management and dataset preparation utility.

---

### error_codes.py

This module provides a set of common error and status codes shared across the package.

The status values are used by acquisition and utility functions to report:

- Successful execution.
- Failed execution.
- Initialization errors.
- Unchecked states.

The file provides a consistent mechanism for handling status reporting throughout the framework.

---

### gen_requests.py

This module provides the `Gen_Requests` class, which acts as an HTTP client for communicating with the external generation server.

Its functionality includes:

- Sending initialization requests to the generator server.
- Establishing synchronization with the DUT communication server.
- Sending single acquisition requests.
- Sending bucket-based acquisition requests.
- Managing REST API communication between the capture framework and the packet generation infrastructure.

This file is mainly used when DUT operations are generated through an external service rather than directly from the acquisition script.

---