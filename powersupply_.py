import os
import time
import glob
import pyvisa
import xml.etree.ElementTree as ET

# ==================================================
# USER CONFIGURATION
# ==================================================

TCML_ROOT_FOLDER = r"C:\ProgramData\Keysight\SequencerUI"

POWER_SUPPLY_RESOURCE = "USB0::0x2A8D::0x0002::MY56312809::0::INSTR"

CHANNEL = 1

CURRENT_LIMIT_A = 1.0  # adjust to a safe/appropriate limit for your DUT

VOLTAGE_MAP = {
    "MAXIMUM": 4.3,
    "MINIMUM": 3.4,
    "NOMINAL": 3.8,
}

# ==================================================
# FIND THE CURRENT TCML FILE
# ==================================================

def get_current_tcml(root_folder):
    pattern = os.path.join(root_folder, "**", "*.tcml")
    files = glob.glob(pattern, recursive=True)

    if not files:
        raise FileNotFoundError(f"No TCML file found under {root_folder}")

    if len(files) > 1:
        print(f"[WARN] Multiple TCML files found, using first: {files}")

    return files[0]

# ==================================================
# READ VOLTAGE CONDITION
# ==================================================

def read_voltage_from_tcml(tcml_file):
    tree = ET.parse(tcml_file)
    root = tree.getroot()

    voltage_condition = None
    for parameter in root.iter("Parameter"):
        if parameter.get("id") == "VoltageConditions":
            voltage_condition = parameter.get("value").strip().upper()
            break

    if voltage_condition is None:
        raise ValueError("VoltageConditions not found in TCML")

    if voltage_condition not in VOLTAGE_MAP:
        raise ValueError(f"Unsupported VoltageConditions value: {voltage_condition}")

    return VOLTAGE_MAP[voltage_condition]

# ==================================================
# CONNECT TO N6700C
# ==================================================

def connect_power_supply():
    rm = pyvisa.ResourceManager()
    print("[DEBUG] Available resources:", rm.list_resources())

    psu = rm.open_resource(POWER_SUPPLY_RESOURCE)
    psu.timeout = 5000

    idn = psu.query("*IDN?")
    print(f"[DEBUG] Connected to: {idn.strip()}")

    return psu

# ==================================================
# SET VOLTAGE
# ==================================================

def set_voltage(psu, voltage):
    # Set current limit first, in case the module blocks output without it
    psu.write(f"CURR {CURRENT_LIMIT_A},(@{CHANNEL})")

    # Clear any latched protection fault before enabling output
    psu.write(f"OUTP:PROT:CLE (@{CHANNEL})")

    psu.write(f"VOLT {voltage},(@{CHANNEL})")
    psu.write(f"OUTP ON,(@{CHANNEL})")

    # Check for SCPI errors
    error = psu.query("SYST:ERR?")
    print(f"[DEBUG] SYST:ERR? -> {error.strip()}")

    # Read back actual setpoint and output state
    readback = psu.query(f"VOLT? (@{CHANNEL})")
    print(f"[DEBUG] Voltage setpoint : {readback.strip()}")

    output_state = psu.query(f"OUTP? (@{CHANNEL})")
    print(f"[DEBUG] Output state: {output_state.strip()}")

    measured = psu.query(f"MEAS:VOLT? (@{CHANNEL})")
    print(f"[DEBUG] Measured output voltage: {measured.strip()}")

# ==================================================
# MAIN LOOP
# ==================================================

def main():
    try:
        tcml_file = get_current_tcml(TCML_ROOT_FOLDER)
        voltage = read_voltage_from_tcml(tcml_file)

        print(f"[INFO] TCML file: {tcml_file}")
        print(f"[INFO] Target voltage: {voltage} V")

        psu = connect_power_supply()
        set_voltage(psu, voltage)
        psu.close()

        print(f"[INFO] Voltage Set = {voltage} V")

    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    while True:
        main()
        time.sleep(20)