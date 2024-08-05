# Imports
import os
import requests
import json
import datetime as dt
import pytz
import dateutil.parser as parser

# API initialization
API_KEY = os.environ.get("API_KEY")
USER_NAME = os.environ.get("USER_NAME")
API_URL = "https://acuityscheduling.com/api/v1/"
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json"
}
# Current date as UTC for easier manipulation later
current_date = dt.datetime.now(pytz.timezone("UTC"))

# Import staff calendar details from file
with open("staff_details.json") as f:
    staff_details = json.load(f)


# Function to get appointments with custom parameters
def get_appointments(params):
    response = requests.get(
        url=API_URL + "appointments",
        auth=(USER_NAME, API_KEY),
        params=params,
        headers=HEADERS
    )

    return response.json()


# Create appointments based on student and date info, passing in calendar ID for staff member
def create_appointment(student, date, calendar):
    data = {
        "datetime": date,
        "appointmentTypeID": student["appointmentTypeID"],
        "calendarID": calendar,
        "firstName": student["firstName"],
        "lastName": student["lastName"],
        "email": student["email"],
        "phone": student["phone"]
    }
    return requests.post(
        url=API_URL + "appointments",
        auth=(USER_NAME, API_KEY),
        headers=HEADERS,
        json=data,
        params={
            "noEmail": "true",
            "admin": "true"
        }
    )


# Cycle through each staff member to find appointments from between 20 and 24 weeks away
for staff in staff_details:
    from_date = current_date + dt.timedelta(weeks=20)
    parameters = {
        "minDate": from_date,
        "maxDate": from_date + dt.timedelta(weeks=4),
        "calendarID": staff["calendar"],
        "max": "200"
    }
    results = get_appointments(parameters)
    students_to_add = []
    previous_student = ""

    for lesson in results:
        # Initialize data to be stored in students_to_add array if criteria are met. Calculate number of occurrences to
        # determine frequency of lessons
        student_details = {
            'firstName': lesson["firstName"],
            'lastName': lesson["lastName"],
            'email': lesson["email"],
            'appointmentTypeID': lesson["appointmentTypeID"],
            'occurrences': len([student for student in results if
                                student["email"] == lesson["email"] and student["time"] == lesson["time"]]),
            'date': lesson["datetime"],
            'time': lesson["time"],
            'phone': lesson["phone"]
        }
        # If an online form is filled out, exclude student from students_to_add
        is_online_form = bool(
            [form for form in lesson["forms"][0]["values"] if form["fieldID"] == 4964051 and form["value"] == "yes"])

        if not is_online_form:
            # If student's email is the same as the previous student, they must be related. So if their lesson times are
            # different, add them as a separate student. Otherwise, if the student is not already present in the array,
            # add them to it
            if lesson["email"] == previous_student and not any(
                    d["lastName"] == lesson["lastName"] and d["time"] == lesson["time"] for d in students_to_add):
                students_to_add.append(student_details)
            elif not any(d["firstName"] == lesson["firstName"] and d["lastName"] == lesson["lastName"] for d in
                         students_to_add):
                students_to_add.append(student_details)

        previous_student = lesson["email"]

    for student in students_to_add:
        date_list = []
        # Work out the number of days to add between the new appointments based on the number of occurrences over the
        # four-week period
        if int(student["occurrences"]) >= 4:
            days = 7
        else:
            days = 14
        parameters = {
            "email": student["email"],
            "minDate": current_date + dt.timedelta(weeks=24),
            "maxDate": from_date + dt.timedelta(weeks=36),
            "calendarID": staff["calendar"],
            "max": "30",
            "excludeForms": "true"
        }

        # Get existing appointments for each student for the rest of the year, to determine the date last booked
        student_results = get_appointments(parameters)

        for result in student_results:
            if result["time"] == student["time"]:
                last_date_booked = parser.parse(result["datetime"]).replace(tzinfo=pytz.timezone("UTC"))
                break

        # Iterate period from last date booked to a year from now, creating array of new dates to book
        while last_date_booked < (current_date + dt.timedelta(weeks=52)):
            new_date = (last_date_booked + dt.timedelta(days=days))
            # Remove timezone from dates (this is automatically done by the Acuity server)
            date_list.append(dt.datetime.isoformat(new_date.replace(tzinfo=None)))
            last_date_booked = new_date

        # Create an appointment on each date from the array
        for date in date_list:
            create_appointment(student, date, staff["calendar"]).json()
