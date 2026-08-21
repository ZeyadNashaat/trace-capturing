import requests
from .error_codes import *

class Gen_Requests():
    """
    This class is used to perform requests from the gen_server on the machine
    """
    def __init__(self, base_url:str = "http://127.0.0.1:8080"):
        """
        The initialization of the class. 
        It has dictionaries to specify the inputs for each endpoint and the available urls by the server 
        
        Args:
            base_url (str): string for the base url of the gen_server
        """
        
        self.urls_available = {
            "init": f"{base_url}/gen/gen_init",
            "connect_to_client_socket": f"{base_url}/gen/gen_connect_to_client_socket",
            "send_packet": f"{base_url}/gen/gen_send_packet",
            "send_buckets": f"{base_url}/gen/gen_send_buckets"    
        }
        
        self.init_params = {
            "port": "/dev/hercules_dut_uart",
            "baudrate": 115200,
            "timeout": 1,
            "log_level": "INFO",
            "socket_host": "10.54.102.246",
            "socket_port": 65432,
            "socket_timeout": 10
        }
        
        self.send_packet_params = {
            "packet_cmd": "",
            "data_buf": "",
            "blocks_write": 0,
            "blocks_read": 1,
            "key": bytearray(24).hex(),
            "buf_offset": 0
        }
        
        self.send_buckets_params = {
            "bucket_cmd": "",
            "data_bucket": "",
            "key_bucket": bytearray(24).hex(),
            "block_to_write": 0,
            "blocks_to_read": 1,
            "buff_offset": 0,
            "total_num_traces": 1000,
            "bucket_size": 100
        }
        
    def request_endpoint(self, endpoint_url:str, inputs:dict):
        """
        This API is used to request a specific endpoint from the server.
        
        Args:
            endpoint_url (str): string for the url. Use from `urls_available` dictionary
            inputs (dict): dictionary for the inputs needed by the endpoint. Use the available dictionaries from the class 
        """
        r =requests.post(endpoint_url,json=inputs)
        r.raise_for_status()