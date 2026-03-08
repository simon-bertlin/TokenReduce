## TokenReduce
Finds the minimal character representation for a given JSON or XML input by converting it to viable formats such as JSON compact, YAML or toon.

## Install 
`python3 -m venv .venv`  
`source .venv/bin/activate`  
`pip install xmltodict toml pyyaml python-toon` or `pip install -r requirements.txt`  

## Run

Remove `example_` from the file `example_input` or `example_xml_input` then run `python3 converter.py`

## Test

`python3 test_converter.py`