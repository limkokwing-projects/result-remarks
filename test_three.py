import asyncio
from turtle import title
import openpyxl
from browser import Browser
from credentials import read_credentials, write_credentials
from html_utils import get_background
from model import Course, CourseGrades, Student
from test_pages.files import test_pages
from bs4 import BeautifulSoup, ResultSet, Tag
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.workbook.workbook import Workbook
from openpyxl.cell.cell import Cell
from openpyxl.utils.dataframe import dataframe_to_rows
from bs4.element import Tag
from rich import print
from rich.console import Console
from rich.prompt import Prompt
from utils.common import convert_list_to_dict

from utils.excel import delete_empty_columns, fit_column_width, is_merged_cell, set_value

PARSER = "html5lib"


console = Console()
error_console = Console(stderr=True, style="bold red")
browser = Browser()


def input_username_and_password():
    username = Prompt.ask("Username")
    password = Prompt.ask("Password", password=True)
    display_name = browser.login(username, password)
    if not display_name:
        error_console.print("Invalid Credentials")
    else:
        write_credentials(username, password)
        print()
    return display_name


async def login():
    username, password, logged_in = None, None, False
    credentials = read_credentials()
    if credentials:
        username, password = credentials
        logged_in = await browser.login(username, password)
    else:
        print("Enter CMS credentials")
        logged_in = input_username_and_password()

    while not logged_in:
        logged_in = input_username_and_password()


def __get_course_names(tr: Tag):
    data = []
    td: Tag
    for i, td in enumerate(tr.find_all('td')):
        text = td.get_text(strip=True)
        if i == 0:
            continue
        if text == 'No. of Module(s)':
            break
        data.append(text)
    return data


def __get_course_codes(tr: Tag):
    data = []
    td: Tag
    for i, td in enumerate(tr.find_all('td')):
        text = td.get_text(strip=True)
        if i == 0:
            continue
        if not text:
            break
        data.append(text)
    return data


def __get_courses(html_table: list[Tag]):
    course_names = __get_course_names(html_table[3])
    course_codes = __get_course_codes(html_table[4])

    data: list[Course] = []
    for i in range(len(course_codes)):
        data.append(
            Course(
                code=course_codes[i],
                name=course_names[i],
            )
        )
    return data


def __read_all_rows(html_table: list[Tag]):
    data = []
    for tr in html_table:
        td_list = tr.find_all('td')
        std_attr = []
        for i, td in enumerate(td_list):
            if i == 0 or i == 3 or i > len(td_list) - 3:
                continue
            text = td.get_text(strip=True)
            if td.get('colspan'):
                span = int(td.get('colspan'))
                std_attr += [None for it in range(span)]
            else:
                std_attr.append(text)
        # -6 so as to remove unneeded data that comes after the last course grades
        data.append(std_attr[:-6])
    return data


def __get_student_data(html_table: ResultSet[Tag]) -> list[Student]:
    data = []
    courses = __get_courses(html_table)
    std_details = __read_all_rows(html_table[7:])

    for it in std_details:
        std_name, std_id = it[0], it[1]
        grades = []
        for i in range(2, len(it), 3):
            course_i = -1
            course_grade = CourseGrades(
                course=courses[course_i := course_i + 1],
                marks=it[i],
                grade=it[i+1],
                points=it[i+2]
            )
            grades.append(course_grade)
        std = Student(id=std_id, name=std_name, grades=grades)
        data.append(std)
    return data


async def __read_transcripts(student_numbers: list[str], semester: int):
    results = {}
    with console.status(f"Reading transcripts..."):
        tasks = []
        for it in student_numbers:
            tasks.append(asyncio.create_task(
                browser.read_transcript(it, semester)))
        data = await asyncio.gather(*tasks)

        for i, it in enumerate(data):
            results[student_numbers[i]] = it

    return convert_list_to_dict(results)


async def generate_remarks(html_table: ResultSet[Tag], semester: int):
    std_grades = __get_student_data(html_table)
    std_numbers = [it.id for it in std_grades]
    transcripts = await __read_transcripts(std_numbers, semester)
    print(transcripts)


async def main():
    while not browser.logged_in:
        await login()

    semester = 1

    with open(test_pages("graderesult.php.html")) as file:
        html = file.read()
        soup = BeautifulSoup(html, PARSER)
        table = soup.select('.ewReportTable tr')
        remarks = await generate_remarks(table, semester)
        # print(remarks)

        # std_details = __get_std_details(table[7:])
        # print(std_details[0])


if __name__ == '__main__':
    asyncio.run(main())
