#!/usr/bin/env python3
import sys
import os
import argparse
import csv
import tomllib
import tomli_w

from pathlib import Path
from dotenv import load_dotenv
from difflib import get_close_matches

from gradescope_api.client import GradescopeClient
from gradescope_api.course import GradescopeCourse
from piazza_api import Piazza

tools_dir = Path(__file__).parent
settings_path = Path(f"{tools_dir}/settings.toml")

def initialize_settings(settings_path):
    if settings_path.exists():
        return
    print(f"Settings file not found, initializing to defaults.")
    default_settings = {
        "course_path" : f"{tools_dir}/courses",
        "courses" : [],
        "default-to-newest" : True,
        "default-length" : 5
    }
    settings_path.write_text(tomli_w.dumps(default_settings))

# config things
def normalize_name(name_str):
    split_name = name_str.split(",")
    if len(split_name) == 1:
        name = split_name[0]
    elif len(name) == 2:
        name = f"{split_name[1].strip()} {split_name[0].strip()}"
    else:
        name = f"{split_name[1].strip()} {split_name[0].strip()}"
    return name

def read_piazza_roster(csv_path):
    roster = {}
    with open(csv_path, newline="") as handle:
        roster_reader = csv.reader(handle)
        header=next(roster_reader)
        for entry in roster_reader:
            if entry[2] == "Student":
                name = normalize_name(entry[0]).lower()
                email = entry[1]
                roster[name] = email
    return roster

def read_gradescope_roster(csv_path):
    roster = {}
    with open(csv_path) as handle:
        roster_reader = csv.reader(handle)
        header = next(roster_reader)
        # name, SID, email, role
        for entry in roster_reader:
            if entry[3] == "Student":
                name = normalize_name(entry[0])
                email = entry[2]
                roster[name] = email
    return roster

def make_course_entry(identifier, gs_id, roster, course_path=Path(f"{tools_dir}/courses")):
    settings = tomllib.loads(settings_path.read_text())
    if identifier in settings["courses"]:
        print(f"WARNING: Course with identifier \"{identifier}\" already exists, overwriting")
    else:
        settings["courses"].append(identifier)
    course_dir = Path(course_path)
    course_dir.mkdir(exist_ok=True)
    
    cfg_path = Path(f"{course_path}/{identifier}.toml")
    cfg = {
        "gradescope-id" : gs_id,
        "roster" : roster
    }
    cfg_path.write_text(tomli_w.dumps(cfg))
    
    if "default-course" not in settings:
        print(f"No default course set, setting to {identifier}.")
        settings["default-course"] = identifier
    elif settings["default-to-newest"]:
        print(f"Setting {identifier} to the default course.")
        settings["default-course"] = identifier
    settings_path.write_text(tomli_w.dumps(settings))

# cli things
def yes_no_helper():
    option = None
    while option is None:
        option = input("(y/N): ").lower()
        if len(option) == 0 or option[0] == "n":
            option = False
        elif option[0] == "y":
            option = True
        else:
            option = None
    return option

def selection_helper(options, msg="Enter a number (i) corresponding to the desired choice:"):
    """
    Return the index from a list of options
    """
    
    print(msg)
    longest_name_len = max(map(lambda x: len(x), options))
    for ix, opt in enumerate(options):
        print(f"  ({ix+1}) {opt}") # course_name:<{longest_name_len}}\t{course.get_term()}\t{course.course_id}")
    ix = None
    while ix is None:
        ix = input("Selection: ")
        if ix.isdigit():
            ix = int(ix)-1
            if ix < 0 or ix >= len(options):
                print(f"{ix+1} not within range. {msg}")
                ix = None
        else:
            ix = None
    return ix

def interactive_setup():
    load_dotenv()
    settings = tomllib.loads(settings_path.read_text())

    print("Connecting to gradescope...\n")
    gs_client = GradescopeClient(email=os.environ["GS_EMAIL"], password=os.environ["GS_PASSWORD"])
    gs_courses = gs_client.get_courses()
    
    longest_name_len = max(map(lambda x: len(x.get_name()), gs_courses))
    gs_course_opt_labels = [f"{course.get_name():<{longest_name_len}}\t{course.get_term()}\t{course.course_id}" for course in gs_courses]
    ix = selection_helper(gs_course_opt_labels, msg="Enter the number (i) of the course to use for configuring:")
    gs_course = gs_courses[ix]

    print("""Do you have csv of the roster?
You can obtain one from gradescope or piazza
For gradescope:
    Roster -> More -> Download Roster
For piazza:
    Manage Class -> Enroll Students -> Download Roster as CSV
Otherwise this will connect to piazza and try to build a roster that way.
""")
    # connect to piazza if available and pull the roster from there
    # connect to gradescope if piazza is not available (student names sometimes don't match)
    
    have_csv = yes_no_helper()

    if have_csv:
        roster_path = Path(input("Enter path to roster csv: "))
        while not roster_path.exists():
            roster_path = Path(input("Path not found, try again: "))
        roster = read_piazza_roster(roster_path)
    else:
        print("\nConnecting to piazza...")
        pz_client = Piazza()
        pz_client.user_login(email=os.environ["PZ_EMAIL"], password=os.environ["PZ_PASSWORD"])
        # TODO: handle case where piazza login fails
        
        pz_courses = [x for x in filter(lambda x: x["is_ta"], pz_client.get_user_classes())]
        longest_name_len = max(map(lambda x: len(x["num"]), pz_courses))
        pz_course_opt_labels = [f"{course['num']:<{longest_name_len}}\t{course['term']}" for course in pz_courses]
        ix = selection_helper(pz_course_opt_labels, "Enter the number (i) of the piazza course to use:")
        pz_course = pz_client.network(pz_courses[ix]["nid"])
        
        students = filter(lambda x: x["role"] == "student", pz_course.get_all_users())
        valid_emails = set(gs_student.email for gs_student in gs_course.get_roster())
        roster = {}
        sans_emails = []
        for student in students:
            name = student["name"].lower()
            emails = student["email"].split(", ")
            valid_email = None
            for email in emails:
                if email in valid_emails:
                    valid_email = email
                    break
            if valid_email is None:
                sans_emails.append(name)
                # probably implement a check to see if that student even is enrolled in gradescope
            else:
                roster[name] = email
        if sans_emails:
            print(f"Warning: could not find an email for the following students. Check to make sure they aren't enrolled on gradescope\n  {'\n  '.join(sans_emails)}")
    
    identifier = None
    while identifier is None:
        identifier = input("\nEnter an identifier to use for this course, no spaces:\n").strip()
        if len(identifier) == 0 or " " in identifier:
            identifier = None
            continue
        if identifier in settings["courses"]:
            print(f"Course with identifier \"{identifier}\" already exists, do you want to overwrite it?")
            if not yes_no_helper():
                identifier = None
    make_course_entry(identifier, gs_course.course_id, roster)

def main():
    global settings
    # check settings are configured
    if not settings_path.exists():
        print("No settings found, initializing settings file")
        initialize_settings(settings_path)
    settings = tomllib.loads(settings_path.read_text())
    load_dotenv()
    if len(settings["courses"]) == 0:
        print("No courses found, entering setup..")
        interactive_setup()
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "extend":
            main_extend(sys.argv[2:])
        elif command == "configure":
            main_configure()
        else:
            print("Right now extend is the only command.")
    else:
        print("Supply a command followed by arguments (e.g. ./gs-tools.py extend -s hw1 student1)")

def main_configure():
    # interactively configure additional courses
    # e.g. adding/modifying students
    # 
    
def main_extend(argv):
    global settings
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--id", choices=settings["courses"], default=settings["default-course"], help="Course identifier")
    parser.add_argument("names", nargs="*", help="student names")
    parser.add_argument("-d", "--days", type=int, default=settings["default-length"], help="Number of days after deadline to extend the assignment. Does not stack with other extensions.")
    # probably default to the most recent assignment? for now just leave it as this
    parser.add_argument("-s", "--string", required=True, help="String for assignment titles to contain (e.g. -s hw4 to apply extension to all assignments with 'hw4' in the title)")
    # parser.add_argument("-r", "--regex", help="Regex string to match assignment titles to")

    args = parser.parse_args(argv)
    if len(args.names) == 0:
        print("No names supplied, exiting..")
        exit(0)
    course_info_path = Path(f"{settings['course_path']}/{args.id}.toml")
    course_info = tomllib.loads(course_info_path.read_text())
    roster = course_info["roster"]

    client = GradescopeClient(email=os.environ["GS_EMAIL"], password=os.environ["GS_PASSWORD"])
    course = client.get_course(course_id=course_info['gradescope-id'])
    assignments = course.get_assignments(args.string)
    print("Processing extensions for the following assignments: ")
    for assign in assignments:
        print("  ", assign.get_name())
    print("For the following students:")
    
    roster_names = list(roster.keys())
    ambig_names = []
    
    for raw_name in args.names:
        student_name = raw_name.lower()
        if student_name not in roster:
            close_matches = get_close_matches(student_name, roster_names, n=5)
            if len(close_matches) == 1:
                email = roster[close_matches[1]]
            if len(close_matches) == 0:
                print(f"{student_name}: could not find in the roster")
                continue
            else:
                print(f"{student_name}: At least {len(close_matches)} found")
                ambig_names.append((student_name, close_matches))
                continue
        else:
            email = roster[student_name]
        print(f"  {student_name} ({email})")
        for assignment in assignments:
            assignment.apply_extension(roster[student_name], args.days)

    for (ambig_name,options) in ambig_names:
        print(f"{ambig_name}: Found the following close matches:")
        ix = selection_helper(options + ["(None)"], msg="Select the number for the correct student (or none if none of these names match)")
        if ix == len(options):
            print(f"Skipping {ambig_name}")
        else:
            student_name = options[ix]
            print(f"  {student_name} ({roster[student_name]})")
            for assignment in assignments:
                assignment.apply_extension(roster[student_name], args.days)

if __name__ == "__main__":
    main()
