from random import randint
import json
import os
from datetime import datetime
from time import perf_counter

from inputimeout import TimeoutOccurred, inputimeout

default_data = {
    "time": 5,
    "questions": 10,
    "minval": 1,
    "maxval": 10,
    "records": [],
}

file = "data.json"
MODES = ["plusonly", "minonly", "timeonly", "divonly", "all"]


class Engine:
    def __init__(self, mode: str, settings: dict):
        self.mode = mode
        self.settings = settings

    def _random_values(self):
        return (
            randint(self.settings["minval"], self.settings["maxval"]),
            randint(self.settings["minval"], self.settings["maxval"]),
        )

    def plus(self):
        int1, int2 = self._random_values()
        return f"{int1} + {int2} = ...", int1 + int2

    def minus(self):
        int1, int2 = self._random_values()
        if int1 < int2:
            int1, int2 = int2, int1
        return f"{int1} - {int2} = ...", int1 - int2

    def times(self):
        int1, int2 = self._random_values()
        return f"{int1} * {int2} = ...", int1 * int2

    def divide(self):
        denominator = randint(self.settings["minval"], self.settings["maxval"])
        if denominator == 0:
            denominator = 1
        quotient = randint(self.settings["minval"], self.settings["maxval"])
        numerator = denominator * quotient
        return f"{numerator} / {denominator} = ...", quotient

    def get_question(self):
        if self.mode == "plusonly":
            return self.plus()
        if self.mode == "minonly":
            return self.minus()
        if self.mode == "timeonly":
            return self.times()
        if self.mode == "divonly":
            return self.divide()
        if self.mode == "all":
            op = randint(1, 4)
            if op == 1:
                return self.plus()
            if op == 2:
                return self.minus()
            if op == 3:
                return self.times()
            if op == 4:
                return self.divide()
        raise ValueError(f"Unsupported mode: {self.mode}")


def play_quiz(data):
    mode = input("Select mode (plusonly/minonly/timeonly/divonly/all): ").strip().lower()
    if mode not in MODES:
        print("Invalid mode selected.")
        return

    engine = Engine(mode=mode, settings=data)
    question_count = data["questions"]
    time_limit = data["time"]
    correct = 0
    incorrect = 0
    started_at = perf_counter()

    for question_number in range(1, question_count + 1):
        question, correct_answer = engine.get_question()
        print(f"Question {question_number}/{question_count}: {question}")

        try:
            user_answer = inputimeout("Your answer: ", timeout=time_limit)
        except TimeoutOccurred:
            incorrect += 1
            print(f"Time's up! The correct answer is {correct_answer}.")
            continue

        try:
            user_answer_number = float(user_answer)
        except ValueError:
            user_answer_number = None

        if user_answer_number is not None and abs(user_answer_number - correct_answer) < 1e-9:
            correct += 1
            print("Correct!")
        else:
            incorrect += 1
            print(f"Incorrect! The correct answer is {correct_answer}.")

    elapsed_time = perf_counter() - started_at
    data.setdefault("records", []).append(
        {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time": time_limit,
            "avg_time": round(elapsed_time / question_count, 2) if question_count else 0,
            "questions": question_count,
            "correct": correct,
            "incorrect": incorrect,
        }
    )
    save_data(data)
    print(f"Quiz complete! Score: {correct}/{question_count}.")


def save_data(data):
    with open(file, "w", encoding="utf-8") as datafile:
        json.dump(data, datafile, indent=4)


def prompt_integer(label, current, minimum=None):
    while True:
        value = input(f"{label} [{current}]: ").strip()
        if not value:
            return current
        try:
            value = int(value)
        except ValueError:
            print("Please enter a whole number, or press Enter to keep the current value.")
            continue
        if minimum is not None and value < minimum:
            print(f"Value must be at least {minimum}.")
            continue
        return value


def edit_settings(data):
    print("\nSettings (press Enter to keep the current value)")
    print(f"Current: {data['time']} sec/question, {data['questions']} questions, "
          f"numbers {data['minval']} to {data['maxval']}")

    updated = data.copy()
    updated["time"] = prompt_integer("Seconds per question", data["time"], minimum=1)
    updated["questions"] = prompt_integer("Number of questions", data["questions"], minimum=1)

    while True:
        minval = prompt_integer("Minimum number", updated["minval"])
        maxval = prompt_integer("Maximum number", updated["maxval"])
        if minval <= maxval:
            updated["minval"] = minval
            updated["maxval"] = maxval
            break
        print("The minimum number must not be greater than the maximum number.")

    save_data(updated)
    data.update(updated)
    print("Settings saved.")


def show_records(data):
    records = data.get("records", [])
    print("\n=== RECORDS ===")
    if not records:
        print("No quiz records yet.")
        return

    for number, record in enumerate(records, start=1):
        print(
            f"{number}. {record['date']} | "
            f"Score: {record['correct']}/{record['questions']} | "
            f"Incorrect: {record['incorrect']} | "
            f"Time: {record['time']} sec | "
            f"Average: {record['avg_time']} sec/question"
        )

def clear():
    print("\033[H\033[J", end="")
