import logging
import secrets
import random
import re
import numpy as np
import os
import h5py
import sys
from tqdm import tqdm

from .error_codes import *


class logger:
    """
    class to manage the logging and its level
    """
    def __init__(self):
        """
        Initializes the logger with an initial level of INFO
        it has an error_state parameter that should be checked to success
        """
        self.level = "INFO"
        self.error_state = ERROR_NOT_CHECKED
        
    def setup_logger(self, level_value: str = "INFO"):
        """
        It is used to set the level of the logger when needed
        
        Args:
            level_value (str): String for defining the level of the logger (default: "INFO") ("INFO", "DEBUG")
        """
        try:
            self.level = getattr(logging, level_value.upper(), logging.INFO)
            logging.basicConfig(level = self.level, format='%(levelname)s: %(message)s')
            self.error_state = SUCCESS
        except Exception as e:
            logging.error(f"Failed to set the logger level: {e}")
            self.error_state = ERROR_MODULE_INIT


class Utilities:
    
    """
    Class for  several utilities needed.
    It has loading traces from files with different extensions. It should load the traces in a numpy array format.
    It has functions to generate plaintexts as randoms or fixed values.
    It has functions to save some metadata to traces of extension h5.
    
    """
    def __init__(self, debug_mode = False):
        """
        Initializes the Utilities with an error_state parameter that should be checked to success.
        Gives a logger for the Utilities to be used
        
        Args:
            debug_mode (bool): Boolean value for enabling debug mood (default: False)
             
        """
        self.error_state = ERROR_NOT_CHECKED
        
        self.debug = debug_mode
        
        self.log = logger()
        if self.debug == True:
            self.log.setup_logger("DEBUG")
            
        else:
            self.log.setup_logger("INFO")
        
        if self.log.error_state != SUCCESS:
            self.error_state = ERROR_MODULE_INIT
        else:
            self.error_state = SUCCESS
            
        self.check_error(exit_on_error=True)
    
    def check_error(self, exit_on_error=True):
        """
        Check for error flag of the Scope class.
        
        Args:
            exit_on_error (bool): Flag to exit on error or not (default: True)
        """        
        
        logging.debug("Start: check_error")
        
        if self.error_state != SUCCESS:
            logging.error("Error in previous function for the scope")
            if exit_on_error:
                sys.exit(1)
                
        logging.debug("End: check_error")
    
    def load_traces_csv(self, path:str = r'', 
                        delimiter = ',', 
                        skip_header = 0, exit_on_error = False):  
        """
        Loading traces from a csv file in a numpy array with the first row of it is the x values
        
        Args:
            path (raw str): raw string with the path of the csv file on oscliscope disk to read the data from 
            delimiter (str): the delimiter of the csv file (default: ',')
            skip_header (int): Number of rows skipped as the header (default: 0)
            exit_on_error (bool): Flag to exit on error or not (default: False) 
        Returns:
            trace_array (numpy array): Numpy Array of traces saved in the file (shape: traces+1, points) 
        """
        logging.debug("Start: load_traces_csv")
        
        self.error_state = ERROR_NOT_CHECKED
        
        data = np.genfromtxt(path, delimiter=delimiter, skip_header=skip_header)
        
        num_cols = data.shape[1]
        rows = []
        if num_cols %2 == 0:

            num_traces = num_cols // 2
            x_ref = data[:, 0]
    
            rows = [x_ref]
            
            for k in range(num_traces):
                yk = data[:, 2 * k + 1]  
                rows.append(yk)
            
            self.error_state = SUCCESS

        else:
            logging.error(f"{path}: Expected an even number of columns (x,y pairs), got {num_cols}")
            self.error_state = FAIL
        
        self.check_error(exit_on_error= exit_on_error)
        
        logging.debug("End: load_traces_csv")
        
        return np.vstack(rows)
    
    
    def load_buckets_csv(self, dir_path: str, delimiter: str = ',', 
                         skip_header: int = 0, files_range: tuple = (),
                         filename_regex: str = r'.*_bucket_(\d+)\.csv$', exit_on_error = False):
        """
        Loading buckets from a directory in a numpy array
        
        Args:
            dir_path (raw str): raw string with the path of the csv file on oscliscope disk to read the data from 
            delimiter (str): the delimiter of the csv file (default: ',')
            skip_header (int): Number of rows skipped as the header (default: 0)
            files_range (tuple): a tuple to load a range of the files from the folder (default: empty)
            filename_regex (str): Regex to be compared with csv file names (default: r'.*_bucket_(\d+)\.csv$')
            exit_on_error (bool): Flag to exit on error or not (default: False) 
        Returns:
            - total_buckets_array (numpyarr): Numpy Array of traces saved in all files (shape: buckets, traces+1, points). 
            - file_order (arr): array for the file order at which they are parsed
        """
        logging.debug("Start: load_buckets_csv")
        
        self.error_state = ERROR_NOT_CHECKED
        
        files = []
        
        for file in os.listdir(dir_path):
            
            m = re.match(filename_regex, file, flags=re.IGNORECASE)
            
            if m and file.lower().endswith('.csv'):
                idx = int(m.group(1))
                files.append((idx, os.path.join(dir_path, file)))
                
        if not files:
            logging.error(f"No CSV files in '{dir_path}' matched regex '{filename_regex}'")
            self.error_state = FAIL
            
        files.sort(key = lambda t: t[0])
        
        bucket_arrays = []
        file_order = []
        
        if not files_range:
            files_range = (0, len(files))
        
        for idx, path in files[files_range[0]:files_range[1]]:
            arr = self.load_traces_csv(path, delimiter=delimiter, skip_header=skip_header, exit_on_error= exit_on_error)

            bucket_arrays.append(arr)
            file_order.append(path)
        
        total_buckets_array = np.stack(bucket_arrays, axis=0)
        
        self.check_error(exit_on_error=exit_on_error)
        
        logging.debug("End: load_buckets_csv")
        
        return total_buckets_array, file_order
    
    def load_traces_h5(self, file_path:str = r'', 
                       channel_name:str = "Channel 5", poi: tuple = (),
                       exit_on_error = False):
        """
        Loading traces from a h5 file in a numpy array
        
        Args:
            file_path (raw str): raw string with the path of the h5 file on oscliscope disk to read the data from 
            channel_name (str): string for the name of channel used to capture the traces
            poi (tuple): a tuple that can be provided to load only hotspots from the traces. (start:end), what is loaded is from start to end
            exit_on_error (bool): Flag to exit on error or not (default: False) 
        Returns:
            traces (numpy array): Numpy Array of traces saved in the file (shape: traces, points)
            x_values (array): An array of horizontal values for that file (shape: points)  
        """
        logging.debug("Start: load_traces_h5")
        try:
            
            file = h5py.File(file_path, 'r')
            logging.debug(f"Groups in file {file_path}")
            logging.debug(list[file.keys()])
            
            waveforms = file['Waveforms'][channel_name]
            logging.debug(f"datasets in the Waveforms group:")
            logging.debug(list[waveforms.keys()])
            
            traces = []
            
            num_segments = waveforms.attrs.__getitem__('NumSegments')
            
            #adding the x values
            x_origin = waveforms.attrs.__getitem__('XOrg')
            x_increment = waveforms.attrs.__getitem__('XInc')
            num_points = waveforms.attrs.__getitem__('NumPoints')
            
            if not poi:
                poi = (0,num_points)
            
            x_values = x_origin + np.arange(num_points, dtype= np.float64) * x_increment
            
            x_values = x_values[poi[0]:poi[1]]
            

            for seg in range(num_segments):
                segment = channel_name + " Seg" + str(seg+1) + 'Data' 
                values = waveforms[segment][poi[0]:poi[1]]
                traces.append(values)
            logging.debug(f"Collected {len(traces)} from file {file_path}")
            
            traces = np.stack(traces)
            self.error_state = SUCCESS
        except Exception as e:
            logging.error(f"Error in the function: {e}")
            self.error_state = FAIL
        
        self.check_error(exit_on_error= exit_on_error)
        
        logging.debug("End: load_traces_h5")
        return traces, x_values
    
    def load_buckets_h5(self, dir_path: str , channel_name: str = "Channel 5", 
                        files_range: tuple = (), poi: tuple = (), 
                        filename_regex: str = r'.*_bucket_(\d+)\.h5$', exit_on_error = False):
        """
        Loading buckets from a directory in a numpy array
        
        Args:
            dir_path (raw str): raw string with the path of the h5 file on oscliscope disk to read the data from 
            channel_name (str): string for the name of channel used to capture the traces
            files_range (tuple): a tuple to load a range of the files from the folder
            poi (tuple): a tuple that can be provided to load only hotspots from the traces. (start:end), what is loaded is from start to end
            filename_regex (str): Regex to be compared with h5 file names (default: r'.*_bucket_(\d+)\.h5$')
            exit_on_error (bool): Flag to exit on error or not (default: False) 
        Returns:
            buckets_array (numpy array): Numpy Array of traces saved in all files (shape: buckets, traces, points) 
            x_arrays (array): array for all the horizontal values for all files (shape: buckets, points)
            file_order (arr): array for the file order at which they are parsed
        """
        logging.debug("Start: load_buckets_h5")
        
        self.error_state = ERROR_NOT_CHECKED
        
        files = []
        
        for file in os.listdir(dir_path):
            
            m = re.match(filename_regex, file, flags=re.IGNORECASE)
            
            if m and file.lower().endswith('.h5'):
                idx = int(m.group(1))
                files.append((idx, os.path.join(dir_path, file)))
                
        if not files:
            logging.error(f"No H5 files in '{dir_path}' matched regex '{filename_regex}'")
            self.error_state = FAIL
            
        files.sort(key = lambda t: t[0])
        
        bucket_arrays = []
        x_arrays = []
        file_order = []
        
        if not files_range:
            files_range = (0, len(files))
        
        subset_files = files[files_range[0]:files_range[1]]
        
        for idx, path in tqdm(subset_files, total = files_range[1], 
                              initial= files_range[0],
                              unit= "file",
                              desc= "loading"):
            arr, x_val = self.load_traces_h5(path,channel_name,poi,exit_on_error)

            bucket_arrays.append(arr)
            x_arrays.append(x_val)
            file_order.append(path)
        
        buckets_array = np.stack(bucket_arrays, axis=0)
        
        self.check_error(exit_on_error)
        
        logging.debug("End: load_buckets_h5")
        
        return buckets_array, x_arrays, file_order
    
    def generate_plaintexts(self, count: int, 
                            block_size: int, mode: str = "random", 
                            seed: int = None, exit_on_error = False):
        """
        Generate a list of bytearrays ("plaintexts") according to the selected mode.
        
        Args:
            count (int): Number of plaintexts to generate (size of the outer array). Must be >= 0.
            block_size (int): Size of each plaintext in bytes (size of each inner byte array). Must be >= 0.
            mode (str): string to identify the mode used for generating the plaintexts
                - "random": cryptographically random bytes
                - "zeros" : all 0x00 bytes
                - "ff"    : all 0xFF bytes
            seed (int): If provided and mode == "random", use a deterministic PRNG (for reproducible tests). If None, use cryptographically strong randomness.
            exit_on_error (bool): Flag to exit on error or not (default: False) 
        Returns:
            plaintexts (list): A list with `count` elements; each element is a `bytearray` of length `block_size` Or None if error
        """
        logging.debug("Start: generate_plaintexts")
        
        self.error_state = ERROR_NOT_CHECKED
        plaintexts = []
        
        try:
            if mode not in ("random", "zeros", "ff"):
                logging.error('mode must be one of: "random", "zeros", "ff"')
                self.error_state = FAIL
            else:
                if mode == "zeros":
                    buf = bytes([0x00]) * block_size
                    plaintexts = [bytearray(buf) for _ in range(count)]

                elif mode == "ff":
                    buf = bytes([0xFF]) * block_size
                    plaintexts = [bytearray(buf) for _ in range(count)]
                
                else:
                    if seed is None:
                        plaintexts = [bytearray(secrets.token_bytes(block_size)) for _ in range(count)]
                    else:
                        rng = random.Random(seed)
                        plaintexts = [bytearray(rng.getrandbits(8) for _ in range(block_size)) for _ in range(count)]
                self.error_state = SUCCESS
        except Exception as e:
            logging.error(f"error in generate_plaintexts: {e}")
            self.error_state = FAIL
        
        if self.error_state != SUCCESS:
            plaintexts = None
        
        self.check_error(exit_on_error= exit_on_error)
        logging.debug("End: generate_plaintexts")
        
        return plaintexts
        
    def generate_random_plaintexts(self, count:int, block_size:int, 
                                   flip_seed: int, fixed_seed:int, random_seed:int, 
                                   mood:str = "random", bias:float = 0.5, 
                                   exit_on_error = False):
        """
        Generate a list of bytearrays ("plaintexts") as a random values or fixed byte array in a random way.
        
        Args:
            count (int): Number of plaintexts to generate (size of the outer array). 
            block_size (int): Size of each plaintext in bytes (size of each inner byte array).
            flip_seed (int): seed used in generating the flipping between random and fixed plaintexts
            fixed_seed (int): seed used in generating the fixed byte array value
            random_seed (int): seed to egenrate the random byte array values
            mood (str): the mood to generate the fixed plaintexts (default: "random")
                - "random": cryptographically random bytes
                - "zeros" : all 0x00 bytes
                - "ff"    : all 0xFF bytes 
            bias (float): Bias to determine the generation of random or fixed values (between 0 and 1)
            exit_on_error (bool): Flag to exit on error or not (default: False)
        
        Returns:
            rand_ids (list): A list of boolean flag to determine if this is a random plaintext (True) or a fixed (False), None if error.
            
            plaintexts (list): A list of the generated plaintexts as a byte array. None if error.
        """
        logging.debug("Start: generate_random_plaintexts")
        
        self.error_state = ERROR_NOT_CHECKED
        
        rand_ids = []
        plaintexts = []
        
        try:
            
            if mood == "ff":
                fixed_plaintext = bytearray([0xFF]* block_size) 
            elif mood == "zeros":
                fixed_plaintext = bytearray([0x00]* block_size) 
            else:
                rng_fixed = random.Random(fixed_seed)
                fixed_plaintext = bytearray(rng_fixed.getrandbits(8) for _ in range(block_size))
            
            rng_rand = random.Random(random_seed)
            
            rng_flip = random.Random(flip_seed)
            
            for _ in range(count):
                value = rng_flip.random()
                if value < bias:
                    rand_ids.append(True)
                    plaintexts.append(bytearray(rng_rand.getrandbits(8) for _ in range(block_size)))
                else:
                    rand_ids.append(False)
                    plaintexts.append(fixed_plaintext)
            
            self.error_state = SUCCESS
            
        except Exception as e:
            logging.error(f"error in generate_random_plaintexts: {e}")
            self.error_state = FAIL
        
        if self.error_state != SUCCESS:
            rand_ids, plaintexts = None
        
        self.check_error(exit_on_error=exit_on_error)
        
        logging.debug("End: generate_random_plaintexts")
        
        return rand_ids, plaintexts
    
    def save_metadata_in_h5traces(self, metadata:list, metadata_name:str, 
                                  file_path:str = r'', group_name:str = "Waveforms/Channel 5", 
                                  num_segments: int = 100, exit_on_error = False):
        """
        Saves metadata for a single h5 file with several traces in it. 
        It appends each metadata to the attribute of each trace.
        
        Args:
            metadata (list): list of the metadata with the same size as traces in file.
            metadata_name (str): string for the name of the attribute.
            file_path (raw str): raw string for the path of the file (default: r'')
            group_name (str): string for the name of the group to find all the traces in (default: "Waveforms/Channel 5")
            num_segments (int): number of traces found in the file (default: 100)
            exit_on_error (bool): Flag to exit on error or not (default: False)
        
        Returns:
            error_state (int): Error code indicating success or failure of the operation  
        """
        logging.debug("Start: save_metadata_in_h5traces")
        
        self.error_state = ERROR_NOT_CHECKED
        try:
            
            with h5py.File(file_path, "r+") as f:
                
                group = f.__getitem__(group_name)
                num_traces = group.attrs['NumSegments']
                logging.debug(f"Number of traces within the file {num_traces}")
                if num_traces == num_segments:
                
                    if len(metadata) == num_segments:
                        
                        match = re.search(r'[^/]+$', group_name)
                        channel_name = match.group(0)
                        logging.debug(f"channel name is {channel_name}")
                
                        for trace in range(num_segments):
                            dataset_name = channel_name+" Seg"+ str(trace+1) + "Data"
                            logging.debug(f"dataset name is {dataset_name}")
                            dataset = group[dataset_name]
                            dataset.attrs[metadata_name] = metadata[trace]
                
                        self.error_state = SUCCESS
                
                    else:
                        logging.error(f"The size of metadata {len(metadata)} inserted does not match the number of traces")
                        self.error_state = FAIL
                
                else:
                    logging.error(f"Number of traces in file {num_traces} does not match the segments needed {num_segments}")
                    self.error_state = FAIL
        except Exception as e:
            logging.error(f"Error in saving metadata {e}")
            self.error_state = FAIL
        
        self.check_error(exit_on_error= exit_on_error)
            
        logging.debug("End: save_metadata_in_h5traces")
        return self.error_state
                
    def save_metadata_in_h5buckets(self, metadata, metadata_name, 
                                   dir_path: str = r'', total_num_traces = 1000, 
                                   bucket_size = 100, group_name:str = "Waveforms/Channel 5", files_range: tuple =(), 
                                   filename_regex: str = r'.*_bucket_(\d+)\.h5$', exit_on_error = False):
        """
        Saves metadata for a multiple h5 files with several traces in it.
        It will parse all the files of h5 in the directory given. 
        It appends each metadata to the attribute of each trace.
        
        Args:
            metadata (list): list of the metadata with the same size total number of traces.
            metadata_name (str): string for the name of the attribute.
            dir_path (raw str): raw string for the path of the directory of files (default: r'')
            total_num_traces: total number of traces in all the files (default: 1000)
            bucket_size (int): number of traces found in a file (default: 100)
            group_name (str): string for the name of the group to find all the traces in (default: "Waveforms/Channel 5")
            files_range (tuple): a tuple to load a range of the files from the folder
            filename_regex (str): Regex to be compared with h5 file names (default: r'.*_bucket_(\d+)\.h5$')
            exit_on_error (bool): Flag to exit on error or not (default: False)
        
        Returns:
            error_state (int): Error code indicating success or failure of the operation
            
            failed_buckets (list): list of failed indices of buckets to save metadata to  
        """
        logging.debug("Start: save_metadata_in_h5buckets")
        
        self.error_state = ERROR_NOT_CHECKED
        
        try:
                
            files = []
            failed_buckets = []
            for file in os.listdir(dir_path):
                
                m = re.match(filename_regex, file, flags=re.IGNORECASE)
                
                if m and file.lower().endswith('.h5'):
                    idx = int(m.group(1))
                    files.append((idx, os.path.join(dir_path, file)))
                    
            if not files:
                logging.error(f"No H5 files in '{dir_path}' matched regex '{filename_regex}'")
                self.error_state = FAIL
                
            files.sort(key = lambda t: t[0])
            
            if not files_range:
                files_range = (0, len(files))
            
            subset_files = files[files_range[0]:files_range[1]]
            
            if len(metadata) == total_num_traces:
                
                for i, (idx, path) in tqdm(
                    enumerate(subset_files),
                    total= files_range[1],
                    initial= files_range[0],
                    unit = "file",
                    desc= "Saving"
                ):
                    logging.debug(f"Saving metadata for bucket {idx}")
                    
                    counter = (i)*bucket_size
                    metadata_bucket = metadata[counter:counter+bucket_size]
                    logging.debug(f"metadata is saved from {counter} to {counter+bucket_size-1}")
                    logging.debug(f"metadata of values {metadata_bucket}")
                    
                    error_state_bucket = self.save_metadata_in_h5traces(metadata=metadata_bucket,
                                                                        metadata_name= metadata_name,
                                                                        file_path= path,
                                                                        group_name= group_name,
                                                                        num_segments= bucket_size)
                    if error_state_bucket != SUCCESS:
                        logging.error(f"Error in saving metadata of bucket {idx}")
                        failed_buckets.append(idx)
                
                if not failed_buckets:
                    self.error_state = SUCCESS
                else:
                    self.error_state = FAIL
                    logging.error(f"Failed to save metadata for buckets {failed_buckets}")
            
            else:
                logging.error(f"metadata size {len(metadata)} does not match the total number of traces")
                self.error_state = FAIL
        
        except Exception as e:
            logging.error(f"Error in saving metadata to buckets {e}")
            self.error_state = FAIL
        
        self.check_error(exit_on_error= exit_on_error)
        
        logging.debug("End: save_metadata_in_h5buckets")
        return self.error_state, failed_buckets
    
    def load_metadata_from_h5traces(self, metadata_name:str, 
                                    file_path: str = r'', group_name: str = "Waveforms/Channel 5", 
                                    num_segments: int = 100, exit_on_error = False):
        """
        Load metadata from a single h5 file with several traces in it. 
        Reads from the metadata of each trace within a specific group.
        
        Args:
            metadata_name (str): string for the name of the attribute.
            file_path (raw str): raw string for the path of the file (default: r'')
            group_name (str): string for the name of the group to find all the traces in (default: "Waveforms/Channel 5")
            poi (tuple): a tuple that can be provided to load only hotspots from the traces.
            num_segments (int): number of traces found in the file (default: 100)
            exit_on_error (bool): Flag to exit on error or not (default: False)
        
        Returns:
            metadata (list): A list for all the metadata within the file. If error, it is an empty list
            
            error_state (int): Error code indicating success or failure of the operation  
        """
        logging.debug("Start: load_metadata_from_h5traces")
        
        self.error_state = ERROR_NOT_CHECKED
        metadata = []
        try:
            
            with h5py.File(file_path, "r") as f:
                
                group = f.__getitem__(group_name)
                num_traces = group.attrs['NumSegments']
                logging.debug(f"Number of traces within the file {num_traces}")
                
                if num_traces == num_segments:
                        
                    match = re.search(r'[^/]+$', group_name)
                    channel_name = match.group(0)
                    logging.debug(f"channel name is {channel_name}")
            
                    for trace in range(num_segments):
                        dataset_name = channel_name+" Seg"+ str(trace+1) + "Data"
                        logging.debug(f"dataset name is {dataset_name}")
                        dataset = group[dataset_name]
                        metadata.append(dataset.attrs[metadata_name][:])
            
                    self.error_state = SUCCESS
                else:
                    logging.error(f"Number of traces in file {num_traces} does not match the segments needed {num_segments}")
                    self.error_state = FAIL
        except Exception as e:
            logging.error(f"Error in loading metadata {e}")
            self.error_state = FAIL
            metadata = []
        
        self.check_error(exit_on_error= exit_on_error)
            
        logging.debug("End: load_metadata_from_h5traces")
        return metadata, self.error_state
    
    def load_metadata_from_h5buckets(self, metadata_name, dir_path: str = r'', 
                                     bucket_size = 100, group_name:str = "Waveforms/Channel 5", 
                                     files_range: tuple =(), filename_regex: str = r'.*_bucket_(\d+)\.h5$', 
                                     exit_on_error = False):
        """
        Loades metadata from a multiple h5 files with several traces in it.
        It will parse all the files of h5 in the directory given and read the metadata of each trace
        
        Args:
            metadata_name (str): string for the name of the attribute.
            dir_path (raw str): raw string for the directory at which files are
            bucket_size (int): number of traces found in a file (default: 100)
            group_name (str): string for the name of the group to find all the traces in (default: "Waveforms/Channel 5")
            files_range (tuple): a tuple to load a range of the files from the folder
            filename_regex (str): Regex to be compared with h5 file names (default: r'.*_bucket_(\d+)\.h5$')
            exit_on_error (bool): Flag to exit on error or not (default: False)
        
        Returns:
            metadata (list): A list for all the metadata within the files of the directory. If error, it is an empty list
            
            failed_buckets (list): list of failed indices of buckets to read metadata from  
        """
        
        logging.debug("Start: load_metadata_from_h5buckets")
        
        self.error_state = ERROR_NOT_CHECKED
        
        try:
                
            files = []
            failed_buckets = []
            metadata = []
            for file in os.listdir(dir_path):
                
                m = re.match(filename_regex, file, flags=re.IGNORECASE)
                
                if m and file.lower().endswith('.h5'):
                    idx = int(m.group(1))
                    files.append((idx, os.path.join(dir_path, file)))
                    
            if not files:
                logging.error(f"No H5 files in '{dir_path}' matched regex '{filename_regex}'")
                self.error_state = FAIL
                
            files.sort(key = lambda t: t[0])
            
            if not files_range:
                files_range = (0, len(files))
                
            subset_files = files[files_range[0]:files_range[1]]
                
            for idx, path in tqdm(subset_files, total = files_range[1], 
                                initial= files_range[0],
                                unit= "file",
                                desc= "loading"):
                logging.debug(f"loading metadata from bucket {idx}")
                
                metadata_bucket, error_state_bucket = self.load_metadata_from_h5traces(metadata_name= metadata_name,
                                                                      file_path= path,
                                                                      group_name= group_name,
                                                                      num_segments= bucket_size,
                                                                      exit_on_error= exit_on_error)
                
                if error_state_bucket != SUCCESS:
                    logging.error(f"Error in loading metadata from bucket {idx}")
                    failed_buckets.append(idx)
                else:
                    metadata.extend(metadata_bucket)
            
            if not failed_buckets:
                self.error_state = SUCCESS
            else:
                self.error_state = FAIL
                logging.error(f"Failed to load metadata from buckets {failed_buckets}")
        
        
        except Exception as e:
            logging.error(f"Error in loading metadata to buckets {e}")
            self.error_state = FAIL
        
        self.check_error(exit_on_error= exit_on_error)
        
        logging.debug("End: load_metadata_from_h5buckets")
        return metadata, failed_buckets