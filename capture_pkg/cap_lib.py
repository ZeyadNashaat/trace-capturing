import sys
import os
import re
import ntpath
import pyvisa
import logging
import socket
import numpy as np
import threading
import h5py
from tqdm import tqdm

from .error_codes import *
from .utilities import logger

class Scope:
    """
    Main class for initilaizng and controlling the scope using PYVISA module.
    
    This class handles the complete workflow of initializing, connecting to the scope.  

    It also manages sending commands to capture traces in asynchronous mode and synchrounus mode.
    The synchronization is implemented using the sockets module.  

    Synchronization happens by sending a flag from the capturing mechanism through socket.
    The target then sends the commands after recieving the flag
    
    It has an attribute error_state which is checked autmatically for the success or failure for the initialization of the class
    
    Attributes:
        error_state (int): defines the error state for the scope
        log (logger): class for initializing logger
        trigger_config (dictionary): dictionary to configure the trigerring mechanism of the scope
        waveform_config (dictionary): dictionary to configure the captured waveform of the scope
        channel_config (dictionary): dictionary to configure the channels used by the scope
    """
    def __init__(self, visa_address: str, scope_timeout = 20000, debug_mode:bool = False):
        """
        Initialize the Scope class with VISA communication parameters and socket communication parameter.
        it has an error_state parameter that is be checked to be SUCCESS automatically.
        
        Args:
            visa_address (str): visa address of the scope
            scope_timeout (int): timeout for scope operations in ms (default: 20000)
            debug_mode (bool): Boolean value for enabling debug mood (default: False)
        """
        
        try:
                
            self.debug = debug_mode
            
            self.log = logger()
            if self.debug == True:
                self.log.setup_logger("DEBUG")
                
            else:
                self.log.setup_logger("INFO")
            
            if self.log.error_state != SUCCESS:
                raise ValueError("Error in initializing the logger")
            
            else:
                
                self.trigger_config = {
                    "mode": "EDGE",        # EDGE or PULSe
                    "source": "CHANnel3",  # Trigger channel
                    "level": 0.6,          # Trigger level in volts
                    "slope": "POSitive",   # POSitive or NEGative
                    "sweep": "TRIGgered"        # AUTO or NORMal
                }
                
                self.channel_config = {
                    "CHANnel3": {
                        "vertical_scale": 0.25,
                        "vertical_offset": 0.5,
                        "horizontal_scale": 4e-7,
                        "horizontal_offset": 1.3e-6
                    },
                    "CHANnel2": {
                        "vertical_scale": 350e-3,
                        "vertical_offset": 0
                    }
                }
                
                self.waveform_config = {
                    "source": "CHANnel2",  # Waveform channel
                    "format": "BYTE",      # BYTE, WORD, ASCII
                    "srate": 2e9,
                    "interpolate": "OFF",
                    "DIMPedance": "FIFTy",
                    "BWLimit": "OFF",
                    "BWType": "BUTTerworth",
                    "BWValue": 300E6
                }
                
                    
                self.rm = pyvisa.ResourceManager('@py')
                self.infinium = self.rm.open_resource(visa_address)
                self.infinium.timeout = scope_timeout
                self.infinium.clear()
                self.do_command(":STOP")
                self.do_command("*CLS")
                self.idn_string = self.do_query_string("*IDN?")
                logging.info(f"The Identification string {self.idn_string}")
                self.do_command("*RST")
                logging.info("Scope is initialized succesfully")
        
        except Exception as e:
            
            logging.error(f"Error in initializing the scope: {e}")
  





    def do_command(self, command, hide_params=False):
        """
        Send a command and check for errors. 
        
        Args:
            command (str): String of the command which is sent to the scope
            hide_params (bool): hide or show the parameters sent by the command (default: False)
        """
        if hide_params:
            (header, data) = command.split(" ", 1)
            logging.debug("\nCmd = '%s'" % header)
        else:
            logging.debug("\nCmd = '%s'" % command)
        
        self.infinium.write("%s" % command)
        
        if hide_params:
            self.check_instrument_errors(header)
        else:
            self.check_instrument_errors(command)

    def do_query_string(self, query):
        """
        Send a query, check for errors
        
        Args:
            query (str): String of the query which is sent to the scope
            
        Returns:
            result (str): returned string result of the query
        """        
        logging.debug("Qys = '%s'" % query)
        result = self.infinium.query("%s" % query)
        self.check_instrument_errors(query)
        
        return result


    def do_query_number(self, query):
        """
        Send a query, check for errors
        
        Args:
            query (str): String of the query which is sent to the scope
            
        Returns:
            result (float): returned float result of the query
        """          
        logging.debug("Qyn = '%s'" % query)
        results = self.infinium.query("%s" % query)
        self.check_instrument_errors(query)
        
        return float(results)


    def do_query_ieee_block(self, query):
        """
        Send a query, check for errors
        
        Args:
            query (str): String of the query which is sent to the scope
            
        Returns:
            result (binary): returned binary result of the query
        """        
        logging.debug("Qyb = '%s'" % query)
        result = self.infinium.query_binary_values("%s" % query, datatype='s', container=bytes)
        self.check_instrument_errors(query)
        
        return result


    def check_instrument_errors(self, command):
        """
        Check for instrument errors. Raises a ValueError if there is a problem
        
        Args:
            command (str): String of the command or query which is sent to the scope
        """
        while True:
            error_string = self.infinium.query(":SYSTem:ERRor? STRing")
            if error_string: # If there is an error string value.
                if error_string.find("0,", 0, 2) == -1: # Not "No error".
                    raise ValueError("ERROR: %s, command: '%s'" % (error_string, command))

                else: # "No error"
                    break
            
            else: # :SYSTem:ERRor? STRing should always return string.
                raise ValueError("ERROR: :SYSTem:ERRor? STRing returned nothing, command: '%s'"% command)
    
    def create_directory_scope(self, full_dir: str):
        """
        Create `full_dir` if it doesn't exist, by listing the parent directory first.
        Args:
            full_dir (str): raw string for the full directory of the file
        """
        logging.debug("Start: create_directory_scope")
        file_exists = None
        
        #splitting the full directory to the parent and file name
        full_dir = full_dir.rstrip("\\/")
        parent = ntpath.dirname(full_dir)
        name = ntpath.basename(full_dir)
        logging.debug(f"parent directory: {parent}")
        logging.debug(f"file name: {name}")
        
        if not parent:
            raise ValueError(f"Cannot determine parent directory from: {full_dir}")

        raw = self.do_query_string(f':DISK:DIRectory? "{parent}"')
        
        #parsing the string into lines in an array
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        first = lines[0]
        m = re.search(r"(-?\d+)\s*$", first)
        n = int(m.group(1))
        entries = lines[1:1+n]  
        
        name = name.strip("\\/")
        for e in entries:
            base = e.strip().strip("\\/") 
            if name.lower() in base.lower() or name.lower() in os.path.basename(base).lower():
                file_exists = True
                break
        
        if not file_exists:
            # Create it
            logging.debug("File did not exist, will create it")
            self.do_command(f':DISK:MDIRectory "{full_dir}"')
        
        logging.debug("End: create_directory_scope")
        
    def connect_to_server_socket(self, server_host = "10.54.102.246", server_port = 65432):
        
        """
        Initializes socket for the client and connect with the server socket. 
        Should be used for synchronization before calling capture_single_trace_sync if the socket was closed before
        
        Args:
            server_host (str): String for defining the host to connect to (default: "10.54.102.246")
            server_port (int): Port number for socket to connect to (default: 65432) 
        
        """

        logging.debug("Start: connect_to_server_socket")
        
        try:
            self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket_client.connect((server_host, server_port))
        except Exception as e:
            logging.error(f"Could not connect to the socket {e}")
        
        logging.debug("End: connect_to_sever_socket")
            
    
    def config_channels(self):
        """
        
        Apply configurations for each channel defined in the dictionary channel_config.
        If an error is raised, it will exit directly.
        
        """
        logging.debug("Start: config_channels")
        try:
            
            self.do_command(":CHANnel1:DISPlay OFF")
            
            for ch_name, settings in self.channel_config.items():
                # Enable channel display
                self.do_command(f":{ch_name}:DISPlay ON")
                
                # Set vertical scale and offset
                self.do_command(f":{ch_name}:SCALe {settings['vertical_scale']}")
                self.do_command(f":{ch_name}:OFFSet {settings['vertical_offset']}")
            
            # Horizontal scale (timebase) is global, so take from first channel or a separate config
            
            first_channel = next(iter(self.channel_config))
            self.do_command(f":TIMebase:SCALe {self.channel_config[first_channel]['horizontal_scale']}")
            self.do_command(f":TIMebase:POSition {self.channel_config[first_channel]['horizontal_offset']}")
        
        except Exception as e:
            logging.error(f"Error in config_channels with {e}")
            sys.exit(1)
        
        logging.info(f"Channels are configured Successfully")
        
        logging.debug("End: config_channels")
    
    def config_trig(self):
        """
        
        Apply configurations for the trigger defined in the dictionary trig_config
        If an error is raised, it will exit directly.
        
        """
        logging.debug("Start: config_trig")
        try:
            
            trig = self.trigger_config

            # Set trigger mode
            self.do_command(f":TRIGger:MODE {trig['mode']}")

            # Set trigger source
            self.do_command(f":TRIGger:{trig['mode']}:SOURce {trig['source']}")

            # Set trigger level
            self.do_command(f":TRIGger:LEVel {trig['source']},{trig['level']}")

            # If EDGE mode, set slope
            if trig['mode'] == "EDGE":
                self.do_command(f":TRIGger:EDGE:SLOPe {trig['slope']}")

            # Set sweep type
            self.do_command(f":TRIGger:SWEep {trig['sweep']}")
            
            logging.debug("Trigger configuration applied:")
            for key, value in trig.items():
                logging.debug(f"  {key}: {value}")
            
        except Exception as e:
            logging.error(f"Error in config_trig with {e}")
            sys.exit(1)    
        
        logging.info("Trigger is configured Successfully")            
        
        logging.debug("End: config_trig")

    def config_waveform(self):
        """
        
        Apply configurations for the waveform defined in the dictionary waveform_config
        If an error is raised, it will exit directly.
        
        """
        logging.debug("Start: config_waveform")
        try:
        
            wf = self.waveform_config

            # Set waveform source (channel)
            self.do_command(f":WAVeform:SOURce {wf['source']}")

            # Set waveform format (BYTE, WORD, ASCII)
            self.do_command(f":WAVeform:FORMat {wf['format']}")
            
            first_channel = next(iter(self.channel_config))
            
            # 10 is the number of horizontal grids of the scope
            waveform_points = round(wf["srate"] * self.channel_config[first_channel]['horizontal_scale']*10)
            self.waveform_config["waveform_points"] = waveform_points
            
            self.do_command(":ACQuire:SRATe:ANALog:AUTO OFF")
            self.do_command(f":ACQuire:SRATe:ANALog {wf['srate']}")
            
            self.do_command(":ACQuire:POINts:AUTO OFF")
            self.do_command(f":ACQuire:POINts:ANALog {waveform_points}")
            
            self.do_command(f":ACQuire:INTerpolate {wf['interpolate']}")
            
            self.do_command(f":SYSTem:DIMPedance {wf['DIMPedance']}")
            
            self.do_command(f':{self.waveform_config["source"]}:ISIM:BWLimit {self.waveform_config["BWLimit"]}')
            self.do_command(f':{self.waveform_config["source"]}:ISIM:BWLimit:TYPE {self.waveform_config["BWType"]}')
            self.do_command(f':{self.waveform_config["source"]}:ISIM:BANDwidth {self.waveform_config["BWValue"]}')
            
            
            logging.debug("Waveform configuration applied:")
            for key, value in wf.items():
                logging.debug(f"  {key}: {value}")
        
        except Exception as e:
            logging.error(f"Error in config_waveform with {e}")
            sys.exit(1) 

        
        logging.info("Waveform is configured Successfully")       
        
        logging.debug("End: config_waveform")          
    
    def save_configurations(self):
        """
        
        save the configurations for the channels, trigger and waveform in a file setup.set
        if there is an error, it will not save properly.
        
        """
        logging.debug("Start: save_configurations")
        
        
        try:
            setup_bytes = self.do_query_ieee_block(":SYSTem:SETup?")
            f = open("setup.set", "wb")
            f.write(setup_bytes)
            f.close()
            logging.info("Setup bytes saved: %d" % len(setup_bytes))
        except Exception as e:
            logging.error(f"Error in save_configurations {e}")
        
        logging.debug("End: save_configurations")
    
    
    def config_scope(self, save_configs: bool = False):
        """
        
        Apply all the configurations for the channels, trigger and waveform
        
        Args:
            save_config (bool): Flag to save configurations or not (default: False)
        
        """
        
        logging.debug("Start: config_scope")
        
        self.config_channels()
        self.config_trig()
        self.config_waveform()
        
        self.do_command(":STOP")
        
        if save_configs:
            self.save_configurations()
        
        logging.debug("End: config_scope")
    
    def auto_scale_time_base(self, pulse_width_range: tuple = (0,100), fill: float = 0.7, 
                            trigger_left_fraction: float = 0.2, exit_on_error: bool = True,
                            thread_semaphore: threading.Semaphore = None):
        """
        It scales the time horizontal base for the scope. It works by arming the scope for a single capture and wait. 
        Then, after capturing, it scales the horizontal scale accordingly. 
        It should be used in a threading mode with a function that sends a command to the DUT.
        
        Args:
            pulse_width_range (tuple): The permitted range of the time of pulse width (seconds) form the (min,max) values (default: (0,100)) 
            fill (float): Percentage by which the trigger should fill the capturing screen (default: 0.7)
            trigger_left_fraction (float): The fraction to be left on the left side of teh trigger (default: 0.2)
            exit_on_error (bool): A flag to exit on error or not (default: True)
            thread_semaphore (threading.Semaphore): A semaphore for synchronization (default: None)
        
        Returns:
            state: returns SUCCESS or FAIL according to the state
        """
        logging.debug("Start: auto_scale_time_base")
        
        try:
            self.do_command(":ACQuire:MODE RTIMe")
            self.do_command(":SINGle")
            
            thread_semaphore.release()
            logging.info("Semaphore is setted")
            
            self.do_query_string("*OPC?")  # Blocks until acquisition finishes
            logging.info("Acquisition complete.")
            
            logging.info("Semaphore is acquired for auto scaling")
            first_channel = next(iter(self.channel_config))
            measure_source = self.trigger_config["source"]
            self.do_command(f":MEASure:SOURce {measure_source}")
            pulse_width = self.do_query_number(":MEASure:PWIDth?")
            logging.info(f"pulse_width: {pulse_width}")
            if pulse_width == None or pulse_width <=pulse_width_range[0] or pulse_width >pulse_width_range[1]:
                raise ValueError("pulse width measured does not fall within the given range")
            
            #10 is the number of divisions on the scope
            scale = pulse_width/(fill*10) 
            pos = (0.5 - trigger_left_fraction) * (10 * scale)
            
            logging.info(f"scale: {scale}")
            logging.info(f"offset: {pos}")
            
            self.do_command(":STOP")
            self.do_command("*CLS")
            self.do_command("*RST")
            self.channel_config[first_channel]['horizontal_scale'] = scale
            self.channel_config[first_channel]['horizontal_offset'] = pos
            self.config_scope()            
            
        except Exception as e:
            logging.error(f"Error in auto_scale_time_base {e}")
            
            if exit_on_error:
                sys.exit(1)
            else:
                return FAIL
        
        logging.debug("End: auto_scale_time_base")
        
        return SUCCESS     
    
    def arm_scope(self, block_arm = True, exit_on_error = True):
        """
        Arming the scope for a single capture mode
        
        Args:
            block_arm (bool): A flag to block after the arming or not (default: True)
            exit_on_error (bool): A flag to exit on error or not (default: True)
        Returns:
            state: state of the function as SUCCESS or FAIL
        """
        logging.debug("Start: arm_scope")
        
        try:
            
            self.do_command(":ACQuire:MODE RTIMe")
            
            
            self.do_command(":SINGle")
            logging.info("Scope is armed successfully")
            if block_arm:
                self.do_query_string("*OPC?")

        except Exception as e:
            logging.error(f"Error in arm_scope {e}")
            if exit_on_error:
                sys.exit(1)
            else:
                return FAIL 
        
        logging.debug("End: arm_scope")    
        
        return SUCCESS
    
    def capture_single_trace_async(self, exit_on_error = True):
        """
        Capture a single trace asynchornous
        
        Args:
            exit_on_error (bool): A flag to exit on error or not (default: True)
            
        Returns:
            waveform_array (array): Array of tuples for the (x_values, y_values). If error, this value is FAIL 
        """
        logging.debug("Start: capture_single_trace_async")
        
        try:
            
            self.do_command(":ACQuire:MODE RTIMe")
            
            # Start acquisition and wait for completion using *OPC?
            self.do_command(":SINGle")
            logging.info("Waiting for acquisition to complete...")
            self.do_query_string("*OPC?")  # Blocks until acquisition finishes
            logging.info("Acquisition complete.")
            
            # Get scaling factors
            x_increment = self.do_query_number(":WAVeform:XINCrement?")
            x_origin = self.do_query_number(":WAVeform:XORigin?")
            y_increment = self.do_query_number(":WAVeform:YINCrement?")
            y_origin = self.do_query_number(":WAVeform:YORigin?")

            # Fetch waveform data
            sData = self.do_query_ieee_block(":WAVeform:DATA?")
            codes = np.frombuffer(sData, dtype=np.int8)
            volts = codes * y_increment + y_origin
            times = x_origin + np.arange(len(sData), dtype= np.float64) * x_increment
            
            # Store in array (list of tuples: time, voltage)
            waveform_array = list(zip(times,volts))

            n_points = self.do_query_number(':WAVeform:POINts?')
            logging.info(f"Captured {n_points} points.")
        
        except Exception as e:
            logging.error(f"Error in capture_single_trace_async {e}")
            if exit_on_error:
                sys.exit(1)
            else:
                return FAIL    
        
        logging.debug("End: capture_single_trace_async")
        
        return waveform_array
    
    def capture_single_trace_sync(self, thread_sync: bool = True, thread_semaphore: threading.Semaphore = None, exit_on_error = True) :
        """
        Capture a single trace synchornous by sending a flag for the target through socket or by a semaphore
        
        Args:
            thread_sync (bool): A flag to indicate which mode of synchronization to work with. True means sync using threading semaphores (default: True)
            thread_semaphore (threading.Semaphore): Semaphore used for synchronization.
            exit_on_error (bool): A flag to exit on error or not (default: True)        
        
        Returns:
            waveform_array (array): Array of tuples for the (x_values, y_values). If error, this value is FAIL 
        """
        logging.debug("Start: capture_single_trace_sync")
        
        try:
            
            self.do_command(":ACQuire:MODE RTIMe")
            
            # Start acquisition and wait for completion using *OPC?
            self.do_command(":SINGle")
            
            if not thread_sync:
            
                self.socket_client.sendall(True.to_bytes(1,'big'))
                logging.info("Flag is sent")
            
            else:
                if thread_semaphore != None:
                    thread_semaphore.release()
                    logging.info("Semaphore is setted")
                else:
                    raise ValueError("Sempahore is not passed correctly")
            
            self.do_query_string("*OPC?")  # Blocks until acquisition finishes
            logging.info("Acquisition complete.")
            
            # Get scaling factors
            x_increment = self.do_query_number(":WAVeform:XINCrement?")
            x_origin = self.do_query_number(":WAVeform:XORigin?")
            y_increment = self.do_query_number(":WAVeform:YINCrement?")
            y_origin = self.do_query_number(":WAVeform:YORigin?")

            # Fetch waveform data
            sData = self.do_query_ieee_block(":WAVeform:DATA?")
            codes = np.frombuffer(sData, dtype=np.int8)
            volts = codes * y_increment + y_origin
            times = x_origin + np.arange(len(sData), dtype= np.float64) * x_increment
            
            # Store in array (list of tuples: time, voltage)
            waveform_array = list(zip(times,volts))
            
            n_points = self.do_query_number(':WAVeform:POINts?')
            logging.info(f"Captured {n_points} points from CHANnel5.")
        except Exception as e:
            logging.error(f"Error in capture_single_trace_sync {e}")
            
            if exit_on_error:
                sys.exit(1)
            else:
                return FAIL
        
        logging.debug("End: capture_single_trace_sync")
        
        return waveform_array      
    
    def capture_segments(self, number_segments = 100, disk_mode = True, 
                         disk_path:str = r'', file_ext:str = "H5", 
                         thread_sync: bool = True, thread_semaphore: threading.Semaphore = None,
                         exit_on_error = True):
        """
        Capture a segment of traces according to the Segmented Acquisition mode  
        It is synchornoused by sending a flag for the target through socket or setting an event to the command generator.
        
        It has two modes for capturing data:
            1. Read the data directly from the oscilscope.
            2. Save the data on the oscilscope disk and read it later.
        
        It has two modes for synchronization:
            1. Synchronization using sockets. Need to call connect_to_server_socket before to initialize the socket
            2. Synchronization using threading semaphores. Pass semaphore for synchronization

        
        Args:
            number_segments (int): Number of segments to be captured (default: 100)
            disk_mode (bool): Flag to indicate the mode to save on disk (default: True)
            disk_path (raw str): raw string with the path on oscliscope disk to save the data in it (default: empty)
            file_ext (str): string for the extension of the saved file (default: "H5")
            thread_sync (bool): A flag to indicate which mode of synchronization to work with. True means sync using threading semaphores (default: True)
            thread_semaphore (threading.Semaphore): Semaphore used for synchronization.
            exit_on_error (bool): A flag to exit on error or not (default: True)
        Returns:
            error_state (int): Error state either success or Fail
            traces_array (array): Array of traces of tuples for the x_values and y_values (shape: segments, points ,2).
                                  if disk_mode or error, it will be empty array 
        """
        logging.debug("Start: capture_segments")
        segment_count = 0
        traces_array = []
        error_state = ERROR_NOT_CHECKED
        
        try:
            
            self.do_command(":ACQuire:MODE SEGMented")
            self.do_command(f":ACQuire:SEGMented:COUNt {number_segments}")
            self.do_command(":WAVeform:SEGMented:ALL ON")
            
            logging.info(f"Arming for {number_segments} segment")
            self.do_command(":SINGLE")
            
            if not thread_sync:
            
                self.socket_client.sendall(True.to_bytes(1,'big'))
                logging.info("Flag is sent")
            
            else:
                if thread_semaphore != None:
                    thread_semaphore.release()
                    logging.info("Semaphore is setted")
                else:
                    raise ValueError("Sempahore is not passed correctly")
            
            self.do_query_string("*OPC?")  # Blocks until acquisition finishes
            logging.info("Acquisition complete.")
            
            preamble_string = self.do_query_string(":WAVeform:PREamble?")
            (
            wav_form, acq_type, wfmpts, avgcnt, x_increment, x_origin,
            x_reference, y_increment, y_origin, y_reference, coupling,
            x_display_range, x_display_origin, y_display_range,
            y_display_origin, date, time, frame_model, acq_mode,
            completion, x_units, y_units, max_bw_limit, min_bw_limit,
            segment_count) = preamble_string.split(",")

            
            expected_bytes = self.waveform_config["waveform_points"] * number_segments
            
            if int(segment_count) == number_segments:
                logging.debug("Number of segments captured matches the number of segments requested")

                if not disk_mode:
                
                    sData = self.do_query_ieee_block(":WAVeform:DATA?")
                    if (len(sData) == expected_bytes):
                        logging.debug("Size of received data matches the needed")
                        
                        for idx in range(1, number_segments+1):
                            start = (idx - 1) * int(wfmpts)
                            end = start + int(wfmpts)
                            seg_bytes = sData[start:end]
                            
                            codes = np.frombuffer(seg_bytes, dtype=np.int8)
                            
                            volts = codes * float(y_increment) + float(y_origin)
                            times = float(x_origin) + np.arange(int(wfmpts), dtype= np.float64) * float(x_increment)
                            traces_array.append(list(zip(times, volts)))
                        
                        logging.info("Traces are appended succesfully")
                    else:
                        raise ValueError(f"Size of received data {len(sData)} mismatches with the needed {expected_bytes}")
            
                else:
                    if disk_path:
                        self.do_command(":DISK:SEGMented ALL")
                        src_channel = self.waveform_config['source']
                        cmd = f':DISK:SAVE:WAVeform {src_channel}, "{disk_path}", {file_ext},OFF'
                        self.do_command(cmd)
                    else:
                        raise ValueError("No file path present to save the captured segments")
                        
            else:
                raise ValueError(f"Number of segments captured {segment_count} does not matches the number of segments requested")
            
            error_state = SUCCESS    
        
        except Exception as e:
            logging.error(f"Error in capture_segments {e}")
            error_state = FAIL
            if exit_on_error:
                sys.exit(1)
        
        logging.debug("End: capture_segments")
        
        return error_state, traces_array
    
    def capture_buckets(self, total_num_traces = 1000, 
                        bucket_size = 100, exit_on_error = True, 
                        disk_mode = True ,file_path = r"", 
                        file_ext:str = "H5", thread_sync: bool = True, 
                        thread_semaphore: threading.Semaphore = None,
                        failed_buckets_file:str = ""
                        ):
        """
        Capture buckets of  segment of traces according to the Segmented Acquisition mode.  
        It is synchornoused by sending a flag for the target through socket after each bucket. It checks error automatically.
        If it is in the disk mode, it will return an empty array
        
        It has two modes for capturing data:
            1. Read the data directly from the oscilscope and save it for .npy file by giving a name to the file 
            2. Save the data on the oscilscope disk to be read later
            
        It has two modes for synchronization:
            1. Synchronization using sockets. Need to call connect_to_server_socket before to initialize the socket
            2. Synchronization using threading semaphores. Pass semaphore for synchronization
        
        Args:
            total_num_traces (int): Total number of traces to capture (default: 1000)
            bucket_size (int): Number of segments to be captured in a bucket (default: 100)
            exit_on_error (bool): Flag to exit on error or not (default: True) 
            disk_mode (bool): Flag to indicate the mode to save on disk (default: True)
            file_path (str): 1. raw string of the directory on oscilscope to save the traces. The directory should not be created yet.  
                             2. Name of the saved .npy file. if empty, it is not saved (default: "")
            file_ext (str): string for the extension of the saved file (default: "H5")
            thread_sync (bool): A flag to indicate which mode of synchronization to work with. True means sync using threading semaphores (default: True)
            thread_semaphore (threading.Semaphore): Semaphore used for synchronization.
            failed_buckets_file (str): Name of h5py file to save the faile buckets in (default: "")
            
        Returns:
            total_buckets (np.array): Array of buckets (shape: number_buckets, traces_per_bucket, points, 2) 
        """
        logging.debug("Start: capture_buckets")
        total_buckets = []
        number_buckets = total_num_traces//bucket_size
        failed_buckets = []
        
        #creating the directory on the scope disk
        last_slash = max(file_path.rfind("/"), file_path.rfind("\\"))
        directory = file_path[:last_slash]
        # cmd = f':DISK:MDIRectory "{directory}"'
        # self.do_command(command=cmd)
        self.create_directory_scope(full_dir= directory)
        
        for i in range(number_buckets):
            logging.info(f"Capturing bucket {i+1}:")
            file_counter = i+1-len(failed_buckets)
            file_name = rf"{file_path}" + rf'_bucket_{file_counter}'
            error_state, traces_bucket = self.capture_segments(bucket_size, disk_mode, 
                                                  disk_path=file_name, file_ext= file_ext, 
                                                  thread_sync= thread_sync, thread_semaphore= thread_semaphore,
                                                  exit_on_error= exit_on_error)
            if error_state == FAIL:
                logging.error(f"Scope: Error in capturing the bucket {i+1}")
                failed_buckets.append(i+1)
                if exit_on_error:
                    sys.exit(1)
            else:
                if disk_mode:
                    logging.info(f"Bucket {i+1} is saved on disk succesfully")
                else:
                    
                    logging.info(f"Bucket {i+1} is collected succesfully")
                    total_buckets.append(traces_bucket)
        
        
        
        if failed_buckets:
            logging.error(f"Failed buckets are{failed_buckets}")
            logging.info("Remove the failed bucket indices from the plaintexts")
            if failed_buckets_file:
                with h5py.File(failed_buckets_file, "a") as f:
                    f.create_dataset("failed_buckets", data=failed_buckets)
                print(f"failed buckets saved into {failed_buckets_file}")

        else:
            logging.info("All buckets are collected susccesfully")
        
        if not disk_mode:            
            total_buckets = np.array(total_buckets)
            if file_path:
                np.save(file_path,total_buckets)
                logging.info(f"Array is saved in file {file_path}")
        
        logging.debug("End: capture_buckets")
        
        return total_buckets 
                
                    
                    
                    
            
            
            
            
        

        
        
        
        

        

            
            
    
    
    
        
        