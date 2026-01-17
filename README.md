# ta-tools
A script for managing gradescope extensions

# Getting started

## Prerequisites
Python version 3.11 or higher with the following python packages installed:
- piazza-api
- python-dotenv
- python-dateutil
- pytz
- requests
- tomli_w

## Setup
1. After installing the required python packages, clone this repo and install the fork of gradescope-api
```sh
git clone https://github.com/reidoko/ta-tools.git
cd ta-tools
# install gradescope-api
git clone https://github.com/reidoko/gradescope-api.git
cd gradescope-api
pip install .
cd ..
```

2. Either set the environment variables `GS_EMAIL` and `GS_PASSWORD` on your system, or create an .env file in the `ta-tools` directory with the corresponding
   login information for gradescope/piazza. Piazza is only used for pulling the class list during configuration.
   If you download the roster csv from Piazza you don't need to bother with it.
```
GS_EMAIL=...
GS_PASSWORD=...
PZ_EMAIL=...
PZ_PASSWORD=...
```

3. Run `./gs-tools.py` with no arguments for the interactive setup process.

Now, you should be able to process extensions with `./gs-tools.py extend`. 
The most recent course that you add is used as the default for trying to apply extensions. 
If you want to change the default class, edit the value of `default-course` in `settings.toml`.

## Usage


### Examples:
Example 1: 2-day extension for a student on all assignments containing the string "hw1"
```sh
./gs-tools.py extend "student name" -s hw1 -d 2
```

Example 2: Grant an extension of default length (set in settings.toml, defaults to 5)
for all of the names in a file `students.txt` for homework with the title "hw1"
```sh
./gs-tools.py extend $(cat students.txt) -s hw1
```

See `./gs-tools.py extend --help` for more info.
