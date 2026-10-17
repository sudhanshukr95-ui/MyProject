import os
import shutil
import pandas as pd
import re

# Temp–Volt → Folder mapping
CONDITIONS = {
    ("55", "4.18"): "thvh",
    ("-10", "3.42"): "tlvl",
    ("-10", "4.18"): "tlvh",
    ("55", "3.42"): "thvl",
    ("25", "3.80"): "tnvn"
}

# Clean Temp/Volt values
def clean(val):
    val = str(val).replace("*", "").replace(" ", "").strip()
    if val.endswith(".0"): val = val[:-2]
    if val.endswith(".00"): val = val[:-3]
    return val

# Extract TC from filename
def extract_tc_from_filename(filename):
    m = re.search(r"(?i)tc_[a-zA-Z0-9]+_[0-9]+(?:\.[0-9]+)*", filename)
    return m.group(0) if m else "Unknown_TC"

# Extract Band from CSV (column 2)
def extract_band_from_csv(df):
    for _, row in df.iterrows():
        band_raw = str(row[2]).strip()
        if band_raw:
            return clean(band_raw)
    return "Unknown_Band"

def process_csv(path, out, order):
    filename = os.path.basename(path)

    # ALWAYS extract TC first — this prevents NameError
    tc = extract_tc_from_filename(filename)

    # Read numeric rows for Temp/Volt/Band
    df = pd.read_csv(path, skiprows=9, header=None)

    temps = []
    volts = []

    # Extract Temp & Volt
    for _, row in df.iterrows():
        temp_raw = str(row[0])
        volt_raw = str(row[1])

        if not any(ch.isdigit() for ch in temp_raw):
            continue
        if not any(ch.isdigit() for ch in volt_raw):
            continue

        temps.append(clean(temp_raw))
        volts.append(clean(volt_raw))

    if not temps or not volts:
        print(f"No valid Temp/Voltage in {filename}")
        return

    pairs = {(t, v) for t, v in zip(temps, volts)}

    if len(pairs) > 1:
        print(f"ERROR: {filename} has multiple Temp–Volt conditions → {pairs}")
        return

    temp, volt = pairs.pop()

    if (temp, volt) not in CONDITIONS:
        print(f"Unknown Temp–Volt {(temp, volt)} in {filename}")
        return

    tempvolt_folder = CONDITIONS[(temp, volt)]

    # Extract Band
    band = extract_band_from_csv(df)

    # Folder order
    if order == "1":
        dest = os.path.join(out, tempvolt_folder, tc, band)
    elif order == "2":
        dest = os.path.join(out, tc, band, tempvolt_folder)
    elif order == "3":
        dest = os.path.join(out, band, tc, tempvolt_folder)
    else:
        dest = os.path.join(out, tempvolt_folder, tc, band)

    os.makedirs(dest, exist_ok=True)
    shutil.move(path, dest)

    print(f"✔ Sorted {filename} → {dest}")

def main():
    inp = input("Enter folder path where CSV files are stored: ").strip()
    out = input("Enter folder path where sorted folders should be created: ").strip()

    print("\nChoose folder order:")
    print("1 = TempVolt → TC → Band")
    print("2 = TC → Band → TempVolt")
    print("3 = Band → TC → TempVolt")
    order = input("Enter your choice (1/2/3): ").strip()

    os.makedirs(out, exist_ok=True)

    for root, dirs, files in os.walk(inp):
        for f in files:
            if f.lower().endswith(".csv"):
                full_path = os.path.join(root, f)
                process_csv(full_path, out, order)

    print("Done sorting.")

if __name__ == "__main__":
    while True:
        main()
        if input("Process more files? (y/n): ").strip().lower() == "n":
            break
