from capture_pkg.cap_lib import *
from capture_pkg import utilities

def main():
    
    utility = utilities.Utilities()
    scope = Scope("TCPIP0::SCOPE-61::hislip0,4880::INSTR",debug_mode= False, scope_timeout= 240_000)
    scope.config_scope()
    scope.arm_scope(block_arm= False)

  
    
if __name__ == "__main__":
    main()