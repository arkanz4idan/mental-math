import json
import math
from datetime import datetime
from pathlib import Path
from time import perf_counter
import tkinter as tk
from tkinter import messagebox, ttk

import engine


DATA_FILE = Path(__file__).resolve().parent / "data.json"
MODES = {
    "Addition only": "plusonly",
    "Subtraction only": "minonly",
    "Multiplication only": "timeonly",
    "Division only": "divonly",
    "Mixed operations": "all",
}


def load_data():
    engine.file = str(DATA_FILE)
    if not DATA_FILE.exists():
        engine.save_data(engine.default_data.copy())

    with DATA_FILE.open("r", encoding="utf-8") as datafile:
        data = json.load(datafile)

    for key, value in engine.default_data.items():
        data.setdefault(key, value.copy() if isinstance(value, list) else value)
    return data


class MathQuizApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Math Quiz")
        self.geometry("620x520")
        self.minsize(500, 420)

        self.data = load_data()
        self.timer_id = None
        self.next_id = None
        self.quiz_started_at = 0.0
        self.question_deadline = 0.0
        self.question_number = 0
        self.correct = 0
        self.incorrect = 0
        self.current_answer = 0

        self.configure(background="#f4f6fb")
        self.style = ttk.Style(self)
        self.style.configure("TButton", font=("Segoe UI", 11), padding=8)
        self.style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        self.style.configure("Subtitle.TLabel", font=("Segoe UI", 12))
        self.style.configure("Question.TLabel", font=("Segoe UI", 30, "bold"))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.show_home()

    def clear_screen(self):
        self.cancel_callbacks()
        for widget in self.winfo_children():
            widget.destroy()

    def cancel_callbacks(self):
        for callback_id in (self.timer_id, self.next_id):
            if callback_id is not None:
                self.after_cancel(callback_id)
        self.timer_id = None
        self.next_id = None

    def add_page(self, title, subtitle=None):
        self.clear_screen()
        page = ttk.Frame(self, padding=28)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text=title, style="Title.TLabel").pack(pady=(12, 6))
        if subtitle:
            ttk.Label(page, text=subtitle, style="Subtitle.TLabel").pack(pady=(0, 20))
        return page

    def show_home(self):
        page = self.add_page("Math Quiz", "Practice arithmetic at your own pace.")
        buttons = ttk.Frame(page)
        buttons.pack(pady=28)
        ttk.Button(buttons, text="Start", command=self.show_quiz_setup, width=24).pack(pady=7)
        ttk.Button(buttons, text="Settings", command=self.show_settings, width=24).pack(pady=7)
        ttk.Button(buttons, text="Records", command=self.show_records, width=24).pack(pady=7)
        ttk.Button(buttons, text="Exit", command=self.close, width=24).pack(pady=7)

    def show_settings(self):
        page = self.add_page("Settings", "Changes are saved to data.json.")
        fields = (
            ("Seconds per question", "time", 1),
            ("Number of questions", "questions", 1),
            ("Minimum number", "minval", None),
            ("Maximum number", "maxval", None),
        )
        entries = {}
        form = ttk.Frame(page)
        form.pack(pady=12)
        for row, (label, key, _minimum) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=8)
            entry = ttk.Entry(form, width=18)
            entry.insert(0, str(self.data[key]))
            entry.grid(row=row, column=1, padx=10, pady=8)
            entries[key] = entry

        def save_settings():
            updated = {}
            for label, key, minimum in fields:
                raw_value = entries[key].get().strip()
                try:
                    value = int(raw_value)
                except ValueError:
                    messagebox.showerror("Invalid setting", f"{label} must be a whole number.")
                    entries[key].focus_set()
                    return
                if minimum is not None and value < minimum:
                    messagebox.showerror("Invalid setting", f"{label} must be at least {minimum}.")
                    entries[key].focus_set()
                    return
                updated[key] = value

            if updated["minval"] > updated["maxval"]:
                messagebox.showerror(
                    "Invalid range",
                    "The minimum number must not be greater than the maximum number.",
                )
                return

            self.data.update(updated)
            engine.save_data(self.data)
            messagebox.showinfo("Settings saved", "Your settings have been saved.")
            self.show_home()

        actions = ttk.Frame(page)
        actions.pack(pady=20)
        ttk.Button(actions, text="Save settings", command=save_settings).pack(side="left", padx=6)
        ttk.Button(actions, text="Back", command=self.show_home).pack(side="left", padx=6)

    def show_records(self):
        page = self.add_page("Records", "Your previous quiz sessions.")
        records = self.data.get("records", [])
        if not records:
            ttk.Label(page, text="No quiz records yet.", style="Subtitle.TLabel").pack(pady=30)
        else:
            table_frame = ttk.Frame(page)
            table_frame.pack(fill="both", expand=True, pady=8)
            columns = ("date", "score", "incorrect", "time", "average")
            table = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
            headings = {
                "date": ("Date", 155),
                "score": ("Score", 75),
                "incorrect": ("Incorrect", 80),
                "time": ("Time (sec)", 85),
                "average": ("Avg. (sec/q)", 95),
            }
            for column, (heading, width) in headings.items():
                table.heading(column, text=heading)
                table.column(column, width=width, anchor="center")
            scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
            table.configure(yscrollcommand=scrollbar.set)
            table.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            for record in reversed(records):
                table.insert(
                    "",
                    "end",
                    values=(
                        record["date"],
                        f'{record["correct"]}/{record["questions"]}',
                        record["incorrect"],
                        record["time"],
                        record["avg_time"],
                    ),
                )
        ttk.Button(page, text="Back", command=self.show_home).pack(pady=10)

    def show_quiz_setup(self):
        page = self.add_page("Start quiz", "Choose which arithmetic questions to practice.")
        self.mode_var = tk.StringVar(value="Mixed operations")
        ttk.Label(page, text="Operation").pack(pady=(12, 4))
        mode_menu = ttk.Combobox(
            page,
            textvariable=self.mode_var,
            values=list(MODES),
            state="readonly",
            width=28,
        )
        mode_menu.pack(pady=4)
        ttk.Label(
            page,
            text=f'{self.data["questions"]} questions · {self.data["time"]} seconds per question',
        ).pack(pady=16)
        ttk.Button(page, text="Begin", command=self.start_quiz).pack(pady=8)
        ttk.Button(page, text="Back", command=self.show_home).pack(pady=8)

    def start_quiz(self):
        self.mode = MODES[self.mode_var.get()]
        self.quiz_engine = engine.Engine(mode=self.mode, settings=self.data)
        self.question_number = 0
        self.correct = 0
        self.incorrect = 0
        self.quiz_started_at = perf_counter()
        self.show_question_screen()
        self.next_question()

    def show_question_screen(self):
        page = self.add_page("Quiz")
        self.progress_label = ttk.Label(page, style="Subtitle.TLabel")
        self.progress_label.pack(pady=(14, 8))
        self.timer_label = ttk.Label(page, style="Subtitle.TLabel")
        self.timer_label.pack(pady=6)
        self.question_label = ttk.Label(page, style="Question.TLabel")
        self.question_label.pack(pady=20)
        self.answer_entry = ttk.Entry(page, font=("Segoe UI", 16), justify="center", width=20)
        self.answer_entry.pack(pady=8)
        self.answer_entry.bind("<Return>", lambda _event: self.submit_answer())
        self.answer_button = ttk.Button(page, text="Submit answer", command=self.submit_answer)
        self.answer_button.pack(pady=8)
        self.feedback_label = ttk.Label(page, style="Subtitle.TLabel")
        self.feedback_label.pack(pady=8)

    def next_question(self):
        self.next_id = None
        if self.question_number >= self.data["questions"]:
            self.finish_quiz()
            return

        self.question_number += 1
        question, self.current_answer = self.quiz_engine.get_question()
        self.progress_label.config(
            text=f'Question {self.question_number}/{self.data["questions"]} '
            f'· Score {self.correct}/{self.question_number - 1}'
        )
        self.question_label.config(text=question)
        self.answer_entry.config(state="normal")
        self.answer_entry.delete(0, "end")
        self.answer_button.config(state="normal")
        self.feedback_label.config(text="")
        self.answer_entry.focus_set()
        self.question_deadline = perf_counter() + self.data["time"]
        self.update_timer()

    def update_timer(self):
        remaining = self.question_deadline - perf_counter()
        if remaining <= 0:
            self.timer_id = None
            self.submit_answer(timed_out=True)
            return
        self.timer_label.config(text=f"Time remaining: {math.ceil(remaining)} sec")
        self.timer_id = self.after(100, self.update_timer)

    def submit_answer(self, timed_out=False):
        if self.timer_id is not None:
            self.after_cancel(self.timer_id)
            self.timer_id = None
        self.answer_entry.config(state="disabled")
        self.answer_button.config(state="disabled")

        if timed_out:
            self.incorrect += 1
            self.feedback_label.config(text=f"Time's up. The answer was {self.current_answer}.")
        else:
            try:
                answer = float(self.answer_entry.get())
            except ValueError:
                answer = None
            if answer is not None and abs(answer - self.current_answer) < 1e-9:
                self.correct += 1
                self.feedback_label.config(text="Correct!")
            else:
                self.incorrect += 1
                self.feedback_label.config(text=f"Incorrect. The answer was {self.current_answer}.")

        self.next_id = self.after(700, self.next_question)

    def finish_quiz(self):
        elapsed_time = perf_counter() - self.quiz_started_at
        question_count = self.data["questions"]
        record = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "time": round(elapsed_time, 2),
            "avg_time": round(elapsed_time / question_count, 2) if question_count else 0,
            "questions": question_count,
            "correct": self.correct,
            "incorrect": self.incorrect,
        }
        self.data.setdefault("records", []).append(record)
        engine.save_data(self.data)

        page = self.add_page("Quiz complete", f"Final score: {self.correct}/{question_count}")
        ttk.Label(
            page,
            text=f'Incorrect: {self.incorrect}    Total time: {record["time"]} sec',
            style="Subtitle.TLabel",
        ).pack(pady=12)
        ttk.Button(page, text="View records", command=self.show_records).pack(pady=6)
        ttk.Button(page, text="Main menu", command=self.show_home).pack(pady=6)

    def close(self):
        self.cancel_callbacks()
        self.destroy()


if __name__ == "__main__":
    MathQuizApp().mainloop()
