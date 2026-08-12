# bagofholding

Inventory supply stock tracker

## INSTALL for PYTEST

conda create -y -n bhenv -c conda-forge pytest
conda activate bhenv

## TEST

cd tests
pytest -s

## COMMAND LINE OPERATIONS

cd cmdline
python inventory.py

## SERVICE OPERATIONS

cd service
python server.py
open the link in a browser
in browser open inventory.html

CTRL+C will stop the server

## JSON DATA FILE

For both methods the local invenvtory_data.json file will be modified.
If inventory_data.json file not present a new file will be created.

The data file is your database.
