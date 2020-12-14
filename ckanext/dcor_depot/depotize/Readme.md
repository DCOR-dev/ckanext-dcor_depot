# Organize arbitrary RT-DC data into the internal DCOR storage folder hierarchy

The scripts in this directory can also be run manually (without
the package installed).

The general pipeline is:

1. Unpack the data `python unpack.py /path/to/tarred_data.tar`
2. Scan for RT-DC data `python scan.py /path/to/tarred_data.tar_depotize`
3. Create a list of valid RT-DC data `python check.py /path/to/tarred_data.tar_depotize/measurements.txt`
4. Convert to internal DCOR structure `python convert.py /path/to/tarred_data.tar_depotize/check_usable.txt`

These JSON files hold information about the files to be ignored and excluded.

- scan_ancillaries.json: simple `format` string replacement scheme.
- scan_associate_tdms: simple `format` string replacement scheme.
- scan_ignore.json: regexp (Python `reg` module) scheme
