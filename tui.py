import json
import math
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from time import perf_counter

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Center, Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static

import engine


DATA_FILE = Path(__file__).resolve().parent / "data.json"
MODES = (
    ("Addition only", "plusonly"),
    ("Subtraction only", "minonly"),
    ("Multiplication only", "timeonly"),
    ("Division only", "divonly"),
    ("Mixed operations", "all"),
)


def load_data():
    engine.file = str(DATA_FILE)
    if not DATA_FILE.exists():
        engine.save_data(deepcopy(engine.default_data))

    with DATA_FILE.open("r", encoding="utf-8") as datafile:
        data = json.load(datafile)

    for key, value in engine.default_data.items():
        data.setdefault(key, deepcopy(value))
    return data


class HomeScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="home-menu"):
                yield Label("Math Quiz", id="title")
                yield Label("Practice arithmetic at your own pace.", id="subtitle")
                yield Button("Start", id="start", variant="primary")
                yield Button("Settings", id="settings")
                yield Button("Records", id="records")
                yield Button("Exit", id="exit", variant="error")
        yield Footer()

    @on(Button.Pressed)
    def handle_button(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.app.push_screen(SetupScreen())
        elif event.button.id == "settings":
            self.app.push_screen(SettingsScreen())
        elif event.button.id == "records":
            self.app.push_screen(RecordsScreen())
        elif event.button.id == "exit":
            self.app.exit()


class SetupScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="setup-panel"):
                yield Label("Start quiz", id="title")
                yield Label("Choose an operation", id="subtitle")
                yield Select(MODES, value="all", id="mode")
                yield Button("Begin", id="begin", variant="primary")
                yield Button("Back", id="back")
        yield Footer()

    @on(Button.Pressed, "#begin")
    def begin_quiz(self) -> None:
        mode = self.query_one("#mode", Select).value
        self.app.push_screen(QuizScreen(str(mode)))

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        data = self.app.data
        yield Header()
        with Center():
            with Vertical(id="settings-panel"):
                yield Label("Settings", id="title")
                yield Label("Changes are saved to data.json.", id="subtitle")
                with Horizontal(classes="setting-row"):
                    yield Label("Seconds per question")
                    yield Input(str(data["time"]), type="integer", id="time")
                with Horizontal(classes="setting-row"):
                    yield Label("Number of questions")
                    yield Input(str(data["questions"]), type="integer", id="questions")
                with Horizontal(classes="setting-row"):
                    yield Label("Minimum number")
                    yield Input(str(data["minval"]), type="integer", id="minval")
                with Horizontal(classes="setting-row"):
                    yield Label("Maximum number")
                    yield Input(str(data["maxval"]), type="integer", id="maxval")
                yield Button("Save settings", id="save", variant="primary")
                yield Button("Back", id="back")
        yield Footer()

    @on(Button.Pressed, "#save")
    def save_settings(self) -> None:
        values = {}
        for key, label, minimum in (
            ("time", "Seconds per question", 1),
            ("questions", "Number of questions", 1),
            ("minval", "Minimum number", None),
            ("maxval", "Maximum number", None),
        ):
            raw_value = self.query_one(f"#{key}", Input).value.strip()
            try:
                value = int(raw_value)
            except ValueError:
                self.app.notify(f"{label} must be a whole number.", severity="error")
                return
            if minimum is not None and value < minimum:
                self.app.notify(f"{label} must be at least {minimum}.", severity="error")
                return
            values[key] = value

        if values["minval"] > values["maxval"]:
            self.app.notify("Minimum number cannot be greater than maximum number.", severity="error")
            return

        self.app.data.update(values)
        engine.save_data(self.app.data)
        self.app.notify("Settings saved.")
        self.app.pop_screen()

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


class RecordsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="records-panel"):
            yield Label("Records", id="title")
            yield Label("Your previous quiz sessions.", id="subtitle")
            yield DataTable(id="records-table")
            yield Static("No quiz records yet.", id="empty-records")
            with Center():
                yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        records = self.app.data.get("records", [])
        table = self.query_one("#records-table", DataTable)
        empty = self.query_one("#empty-records", Static)
        if not records:
            table.display = False
            empty.display = True
            return

        empty.display = False
        table.add_columns("Date", "Score", "Incorrect", "Time (sec)", "Avg. (sec/q)")
        for record in reversed(records):
            table.add_row(
                record["date"],
                f'{record["correct"]}/{record["questions"]}',
                str(record["incorrect"]),
                str(record["time"]),
                str(record["avg_time"]),
            )

    @on(Button.Pressed, "#back")
    def back(self) -> None:
        self.app.pop_screen()


class QuizScreen(Screen):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.question_number = 0
        self.correct = 0
        self.incorrect = 0
        self.current_answer = 0
        self.started_at = 0.0
        self.deadline = 0.0

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="quiz-panel"):
                yield Label("", id="progress")
                yield Label("", id="timer")
                yield Label("", id="question")
                yield Input(placeholder="Type your answer", id="answer")
                yield Button("Submit answer", id="submit", variant="primary")
                yield Label("", id="feedback")
        yield Footer()

    def on_mount(self) -> None:
        self.quiz_engine = engine.Engine(mode=self.mode, settings=self.app.data)
        self.started_at = perf_counter()
        self.next_question()
        self.set_interval(0.1, self.update_timer)

    def next_question(self) -> None:
        if self.question_number >= self.app.data["questions"]:
            self.finish_quiz()
            return

        self.question_number += 1
        question, self.current_answer = self.quiz_engine.get_question()
        self.query_one("#progress", Label).update(
            f'Question {self.question_number}/{self.app.data["questions"]} '
            f"· Score {self.correct}/{self.question_number - 1}"
        )
        self.query_one("#question", Label).update(question)
        self.query_one("#feedback", Label).update("")
        answer_input = self.query_one("#answer", Input)
        answer_input.value = ""
        answer_input.disabled = False
        self.query_one("#submit", Button).disabled = False
        self.deadline = perf_counter() + self.app.data["time"]
        answer_input.focus()
        self.update_timer()

    def update_timer(self) -> None:
        remaining = self.deadline - perf_counter()
        if remaining <= 0:
            self.submit_answer(timed_out=True)
            return
        self.query_one("#timer", Label).update(f"Time remaining: {math.ceil(remaining)} sec")

    @on(Input.Submitted, "#answer")
    def answer_submitted(self) -> None:
        self.submit_answer()

    @on(Button.Pressed, "#submit")
    def submit_button_pressed(self) -> None:
        self.submit_answer()

    def submit_answer(self, timed_out: bool = False) -> None:
        answer_input = self.query_one("#answer", Input)
        if answer_input.disabled:
            return
        answer_input.disabled = True
        self.query_one("#submit", Button).disabled = True

        if timed_out:
            self.incorrect += 1
            feedback = f"Time's up. The answer was {self.current_answer}."
        else:
            try:
                answer = float(answer_input.value)
            except ValueError:
                answer = None
            if answer is not None and abs(answer - self.current_answer) < 1e-9:
                self.correct += 1
                feedback = "Correct!"
            else:
                self.incorrect += 1
                feedback = f"Incorrect. The answer was {self.current_answer}."

        self.query_one("#feedback", Label).update(feedback)
        self.set_timer(0.7, self.next_question)

    def finish_quiz(self) -> None:
        elapsed_time = perf_counter() - self.started_at
        question_count = self.app.data["questions"]
        record = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time": round(elapsed_time, 2),
            "avg_time": round(elapsed_time / question_count, 2) if question_count else 0,
            "questions": question_count,
            "correct": self.correct,
            "incorrect": self.incorrect,
        }
        self.app.data.setdefault("records", []).append(record)
        engine.save_data(self.app.data)
        self.app.switch_screen(ResultScreen(record))


class ResultScreen(Screen):
    def __init__(self, record: dict) -> None:
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Vertical(id="result-panel"):
                yield Label("Quiz complete", id="title")
                yield Label(
                    f'Score: {self.record["correct"]}/{self.record["questions"]}',
                    id="score",
                )
                yield Label(
                    f'Incorrect: {self.record["incorrect"]} · '
                    f'Total time: {self.record["time"]} sec',
                    id="subtitle",
                )
                yield Button("View records", id="records")
                yield Button("Main menu", id="home", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#records")
    def view_records(self) -> None:
        self.app.push_screen(RecordsScreen())

    @on(Button.Pressed, "#home")
    def go_home(self) -> None:
        self.app.switch_screen(HomeScreen())


class MathQuizTUI(App):
    TITLE = "Math Quiz"
    CSS = """
    Screen {
        align: center middle;
    }
    #home-menu, #setup-panel, #settings-panel, #quiz-panel, #result-panel {
        width: 70;
        height: auto;
        padding: 1 3;
        border: round $primary;
        background: $surface;
        align: center middle;
    }
    #records-panel {
        width: 90%;
        height: 90%;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    #title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 1 0;
    }
    #subtitle {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    #home-menu Button, #setup-panel Button, #result-panel Button {
        width: 34;
        margin: 1 14;
    }
    #settings-panel .setting-row {
        width: 100%;
        height: 3;
        align: left middle;
    }
    #settings-panel .setting-row Label {
        width: 30;
    }
    #settings-panel .setting-row Input {
        width: 20;
    }
    #settings-panel Button {
        width: 34;
        margin: 1 14;
    }
    #quiz-panel #question {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 2 0;
    }
    #quiz-panel #progress, #quiz-panel #timer, #quiz-panel #feedback {
        width: 100%;
        text-align: center;
        margin: 1 0;
    }
    #quiz-panel #answer {
        width: 34;
        margin: 1 0;
    }
    #quiz-panel #submit {
        width: 34;
        margin: 0 14;
    }
    #records-table {
        height: 1fr;
        margin: 1 0;
    }
    #empty-records {
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
    }
    #records-panel #back {
        width: 24;
    }
    #result-panel #score {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $success;
        margin: 1 0;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.data = load_data()

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())


if __name__ == "__main__":
    MathQuizTUI().run()
